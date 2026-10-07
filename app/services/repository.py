"""
Repositorio de datos.

`Repository` es la interfaz que usan los endpoints. Hay dos implementaciones:
- `MemoryRepository`  — todo en memoria (fallback si no hay BD)
- `SqlRepository`     — PostgreSQL via SQLAlchemy

`get_repository()` (en `app.services.store`) devuelve la que corresponda.

Multi-usuario: el perfil, las preferencias y el historial pertenecen a un
usuario concreto (`user_id`). Las frases rapidas son catalogo compartido.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.db.base import (
    Frase,
    HistorialTraduccion,
    ModeloReconocimiento,
    MuestraSena,
    PreferenciaAccesibilidad,
    ReporteReconocimiento,
    Sena,
    Usuario,
    get_session,
)
from app.schemas.auth import AuthUser
from app.schemas.history import HistoryEntry, HistoryEntryCreate
from app.schemas.phrases import QuickPhrase, QuickPhraseGroup
from app.schemas.preferences import Preferences
from app.schemas.profile import Profile
from app.schemas.signs import (
    DatasetLabelCount,
    DatasetSampleStored,
    DatasetSummary,
    RecognitionModel,
    RecognitionReport,
    RecognitionReportCreate,
    Sign,
)
from app.services.vocabulary import SEED_MODELS, seed_signs

CATEGORY_LABELS = {
    "saludos": "Saludos",
    "necesidades": "Necesidades",
    "emergencias": "Emergencias",
}
CATEGORY_ORDER = ["saludos", "necesidades", "emergencias"]


class EmailAlreadyUsed(Exception):
    """El correo ya pertenece a otra cuenta."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_phrases() -> list[QuickPhrase]:
    """Frases semilla. `is_demo=True`: senas LSP no validadas."""
    raw = [
        ("ph-hola", "Hola", "saludos"),
        ("ph-gracias", "Gracias", "saludos"),
        ("ph-por-favor", "Por favor", "saludos"),
        ("ph-ayuda", "Necesito ayuda", "necesidades"),
        ("ph-no-entiendo", "No entiendo", "necesidades"),
        ("ph-bano", "¿Donde esta el bano?", "necesidades"),
        ("ph-emergencias", "Llame a emergencias", "emergencias"),
    ]
    return [
        QuickPhrase(id=i, text=t, category=c)  # type: ignore[arg-type]
        for i, t, c in raw
    ]


def _prefs_to_row(p: Preferences, user_id: int) -> PreferenciaAccesibilidad:
    return PreferenciaAccesibilidad(
        usuario_id=user_id,
        tema=p.theme,
        tamano_texto=p.text_size,
        velocidad_voz=p.voice_speed,
        velocidad_avatar=p.avatar_speed,
        subtitulos=p.subtitles,
        idioma=p.language,
    )


def _row_to_prefs(row: PreferenciaAccesibilidad) -> Preferences:
    """
    Convierte la fila a esquema. Si la BD trae un valor fuera del vocabulario
    (edicion manual, migracion a medias), Pydantic lo rechazaria y tumbaria el
    endpoint: en ese caso se cae a los valores por defecto.
    """
    try:
        return Preferences(
            theme=row.tema,  # type: ignore[arg-type]
            text_size=row.tamano_texto,  # type: ignore[arg-type]
            voice_speed=row.velocidad_voz,  # type: ignore[arg-type]
            avatar_speed=row.velocidad_avatar,  # type: ignore[arg-type]
            subtitles=row.subtitulos,
            language=row.idioma,
        )
    except ValidationError:
        return Preferences()


def _group_phrases(phrases: list[QuickPhrase]) -> list[QuickPhraseGroup]:
    groups: list[QuickPhraseGroup] = []
    for cat in CATEGORY_ORDER:
        items = [p for p in phrases if p.category == cat]
        if items:
            groups.append(
                QuickPhraseGroup(
                    category=cat,  # type: ignore[arg-type]
                    label=CATEGORY_LABELS[cat],
                    phrases=items,
                )
            )
    return groups


def _summary(signs: list[Sign], counts: dict[str, tuple[int, int]]) -> DatasetSummary:
    """Conteo por etiqueta, en el orden del vocabulario."""
    labels = [
        DatasetLabelCount(
            label=sign.label,
            word=sign.word,
            samples=counts.get(sign.label, (0, 0))[0],
            validated_samples=counts.get(sign.label, (0, 0))[1],
        )
        for sign in signs
    ]
    return DatasetSummary(total=sum(c.samples for c in labels), labels=labels)


class Repository(Protocol):
    # ---- Cuentas ----
    def create_user(self, name: str, email: str, password: str) -> AuthUser: ...
    def authenticate(self, email: str, password: str) -> AuthUser | None: ...
    def get_user(self, user_id: int) -> AuthUser | None: ...

    # ---- Datos por usuario ----
    def get_profile(self, user_id: int) -> Profile: ...
    def update_profile(self, user_id: int, name: str, email: str) -> Profile: ...
    def get_preferences(self, user_id: int) -> Preferences: ...
    def update_preferences(self, user_id: int, data: Preferences) -> Preferences: ...
    def list_history(
        self, user_id: int, limit: int | None = None
    ) -> list[HistoryEntry]: ...
    def add_history(self, user_id: int, data: HistoryEntryCreate) -> HistoryEntry: ...
    def delete_history(self, user_id: int, entry_id: str) -> bool: ...
    def clear_history(self, user_id: int) -> int: ...

    # ---- Catalogo compartido ----
    def list_phrase_groups(self) -> list[QuickPhraseGroup]: ...

    # Vocabulario de senas (catalogo compartido)
    def list_signs(self) -> list[Sign]: ...
    def get_sign(self, label: str) -> Sign | None: ...

    # Reconocimiento
    def add_report(
        self, user_id: int | None, data: RecognitionReportCreate
    ) -> RecognitionReport: ...
    def list_models(self) -> list[RecognitionModel]: ...

    # Dataset (registro de muestras; los landmarks viven en archivos)
    def add_sample(self, sample: DatasetSampleStored, consent: bool, notes: str) -> None: ...
    def dataset_summary(self) -> DatasetSummary: ...


# --------------------------------------------------------------------------
# Implementacion en memoria
# --------------------------------------------------------------------------


@dataclass
class _MemUser:
    id: int
    name: str
    email: str
    password_hash: str
    preferences: Preferences = field(default_factory=Preferences)
    history: list[HistoryEntry] = field(default_factory=list)


class MemoryRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users: dict[int, _MemUser] = {}
        self._next_id = 1
        self._phrases = _seed_phrases()
        self._signs = seed_signs()
        self._models = [m.model_copy() for m in SEED_MODELS]
        self._reports: list[RecognitionReport] = []
        self._samples: list[DatasetSampleStored] = []

    # ---- Cuentas ----
    def _find_by_email(self, email: str) -> _MemUser | None:
        target = email.strip().lower()
        return next(
            (u for u in self._users.values() if u.email.lower() == target), None
        )

    def create_user(self, name: str, email: str, password: str) -> AuthUser:
        with self._lock:
            if self._find_by_email(email) is not None:
                raise EmailAlreadyUsed(email)
            user = _MemUser(
                id=self._next_id,
                name=name,
                email=email,
                password_hash=hash_password(password),
            )
            self._users[user.id] = user
            self._next_id += 1
            return AuthUser(id=user.id, name=user.name, email=user.email)

    def authenticate(self, email: str, password: str) -> AuthUser | None:
        with self._lock:
            user = self._find_by_email(email)
            if user is None or not verify_password(password, user.password_hash):
                return None
            return AuthUser(id=user.id, name=user.name, email=user.email)

    def get_user(self, user_id: int) -> AuthUser | None:
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                return None
            return AuthUser(id=user.id, name=user.name, email=user.email)

    def _require(self, user_id: int) -> _MemUser:
        user = self._users.get(user_id)
        if user is None:
            raise KeyError(f"usuario {user_id} no existe")
        return user

    # ---- Perfil ----
    def get_profile(self, user_id: int) -> Profile:
        with self._lock:
            user = self._require(user_id)
            return Profile(name=user.name, email=user.email)

    def update_profile(self, user_id: int, name: str, email: str) -> Profile:
        with self._lock:
            user = self._require(user_id)
            other = self._find_by_email(email)
            if other is not None and other.id != user_id:
                raise EmailAlreadyUsed(email)
            user.name = name
            user.email = email
            return Profile(name=user.name, email=user.email)

    # ---- Preferencias ----
    def get_preferences(self, user_id: int) -> Preferences:
        with self._lock:
            return self._require(user_id).preferences.model_copy()

    def update_preferences(self, user_id: int, data: Preferences) -> Preferences:
        with self._lock:
            user = self._require(user_id)
            user.preferences = data.model_copy()
            return user.preferences.model_copy()

    # ---- Historial ----
    def list_history(
        self, user_id: int, limit: int | None = None
    ) -> list[HistoryEntry]:
        with self._lock:
            items = sorted(
                self._require(user_id).history,
                key=lambda e: e.created_at,
                reverse=True,
            )
            return items[:limit] if limit else list(items)

    def add_history(self, user_id: int, data: HistoryEntryCreate) -> HistoryEntry:
        with self._lock:
            user = self._require(user_id)
            entry = HistoryEntry(
                id=uuid.uuid4().hex[:12],
                created_at=_now(),
                **data.model_dump(),
            )
            user.history.append(entry)
            return entry

    def delete_history(self, user_id: int, entry_id: str) -> bool:
        with self._lock:
            user = self._require(user_id)
            before = len(user.history)
            user.history = [e for e in user.history if e.id != entry_id]
            return len(user.history) < before

    def clear_history(self, user_id: int) -> int:
        with self._lock:
            user = self._require(user_id)
            n = len(user.history)
            user.history = []
            return n

    # ---- Frases ----
    def list_phrase_groups(self) -> list[QuickPhraseGroup]:
        with self._lock:
            return _group_phrases([p.model_copy() for p in self._phrases])

    # ---- Vocabulario ----
    def list_signs(self) -> list[Sign]:
        with self._lock:
            return [sg.model_copy() for sg in self._signs]

    def get_sign(self, label: str) -> Sign | None:
        with self._lock:
            found = next((sg for sg in self._signs if sg.label == label), None)
            return found.model_copy() if found else None

    # ---- Reconocimiento ----
    def add_report(
        self, user_id: int | None, data: RecognitionReportCreate
    ) -> RecognitionReport:
        with self._lock:
            report = RecognitionReport(
                id=uuid.uuid4().hex[:12], created_at=_now(), **data.model_dump()
            )
            self._reports.append(report)
            return report

    def list_models(self) -> list[RecognitionModel]:
        with self._lock:
            return [m.model_copy() for m in self._models]

    # ---- Dataset ----
    def add_sample(self, sample: DatasetSampleStored, consent: bool, notes: str) -> None:
        with self._lock:
            self._samples.append(sample.model_copy())

    def dataset_summary(self) -> DatasetSummary:
        with self._lock:
            counts: dict[str, tuple[int, int]] = {}
            for smp in self._samples:
                n, v = counts.get(smp.label, (0, 0))
                counts[smp.label] = (n + 1, v)
            return _summary(self._signs, counts)


# --------------------------------------------------------------------------
# Implementacion PostgreSQL
# --------------------------------------------------------------------------


class SqlRepository:
    """Repositorio contra PostgreSQL. Una sesion corta por operacion."""

    def _session(self) -> Session:
        return get_session()

    # ---- Cuentas ----
    def create_user(self, name: str, email: str, password: str) -> AuthUser:
        with self._session() as s:
            row = Usuario(
                nombre=name,
                correo=email,
                contrasena_hash=hash_password(password),
                creado_en=_now(),
            )
            s.add(row)
            try:
                s.commit()
            except IntegrityError as exc:
                # El indice unico de `correo` es la garantia real frente a dos
                # registros simultaneos con el mismo correo.
                s.rollback()
                raise EmailAlreadyUsed(email) from exc
            s.refresh(row)
            # Preferencias por defecto para la cuenta recien creada.
            s.add(_prefs_to_row(Preferences(), row.id))
            s.commit()
            return AuthUser(id=row.id, name=row.nombre, email=row.correo)

    def authenticate(self, email: str, password: str) -> AuthUser | None:
        with self._session() as s:
            row = s.scalar(select(Usuario).where(Usuario.correo == email))
            if row is None or not verify_password(password, row.contrasena_hash):
                return None
            return AuthUser(id=row.id, name=row.nombre, email=row.correo)

    def get_user(self, user_id: int) -> AuthUser | None:
        with self._session() as s:
            row = s.get(Usuario, user_id)
            if row is None:
                return None
            return AuthUser(id=row.id, name=row.nombre, email=row.correo)

    # ---- Perfil ----
    def get_profile(self, user_id: int) -> Profile:
        with self._session() as s:
            user = s.get(Usuario, user_id)
            if user is None:
                raise KeyError(f"usuario {user_id} no existe")
            return Profile(name=user.nombre, email=user.correo)

    def update_profile(self, user_id: int, name: str, email: str) -> Profile:
        with self._session() as s:
            user = s.get(Usuario, user_id)
            if user is None:
                raise KeyError(f"usuario {user_id} no existe")
            user.nombre = name
            user.correo = email
            try:
                s.commit()
            except IntegrityError as exc:
                s.rollback()
                raise EmailAlreadyUsed(email) from exc
            return Profile(name=user.nombre, email=user.correo)

    # ---- Preferencias ----
    def get_preferences(self, user_id: int) -> Preferences:
        with self._session() as s:
            row = s.scalar(
                select(PreferenciaAccesibilidad).where(
                    PreferenciaAccesibilidad.usuario_id == user_id
                )
            )
            if row is None:
                defaults = Preferences()
                s.add(_prefs_to_row(defaults, user_id))
                s.commit()
                return defaults
            return _row_to_prefs(row)

    def update_preferences(self, user_id: int, data: Preferences) -> Preferences:
        with self._session() as s:
            row = s.scalar(
                select(PreferenciaAccesibilidad).where(
                    PreferenciaAccesibilidad.usuario_id == user_id
                )
            )
            if row is None:
                s.add(_prefs_to_row(data, user_id))
            else:
                row.tema = data.theme
                row.tamano_texto = data.text_size
                row.velocidad_voz = data.voice_speed
                row.velocidad_avatar = data.avatar_speed
                row.subtitulos = data.subtitles
                row.idioma = data.language
            s.commit()
            return data.model_copy()

    # ---- Historial ----
    def list_history(
        self, user_id: int, limit: int | None = None
    ) -> list[HistoryEntry]:
        with self._session() as s:
            stmt = (
                select(HistorialTraduccion)
                .where(HistorialTraduccion.usuario_id == user_id)
                .order_by(HistorialTraduccion.creado_en.desc())
            )
            if limit:
                stmt = stmt.limit(limit)
            rows = s.scalars(stmt).all()
            return [
                HistoryEntry(
                    id=r.id,
                    direction=r.direccion,  # type: ignore[arg-type]
                    text=r.texto,
                    is_demo=r.es_demo,
                    created_at=r.creado_en,
                )
                for r in rows
            ]

    def add_history(self, user_id: int, data: HistoryEntryCreate) -> HistoryEntry:
        with self._session() as s:
            row = HistorialTraduccion(
                id=uuid.uuid4().hex[:12],
                usuario_id=user_id,
                direccion=data.direction,
                texto=data.text,
                es_demo=data.is_demo,
                creado_en=_now(),
            )
            s.add(row)
            s.commit()
            return HistoryEntry(
                id=row.id,
                direction=row.direccion,  # type: ignore[arg-type]
                text=row.texto,
                is_demo=row.es_demo,
                created_at=row.creado_en,
            )

    def delete_history(self, user_id: int, entry_id: str) -> bool:
        with self._session() as s:
            row = s.get(HistorialTraduccion, entry_id)
            # Comprobar el dueno: sin esto cualquiera podria borrar entradas
            # ajenas conociendo el id.
            if row is None or row.usuario_id != user_id:
                return False
            s.delete(row)
            s.commit()
            return True

    def clear_history(self, user_id: int) -> int:
        with self._session() as s:
            result = s.execute(
                delete(HistorialTraduccion).where(
                    HistorialTraduccion.usuario_id == user_id
                )
            )
            s.commit()
            return int(result.rowcount or 0)

    # ---- Frases ----
    def list_phrase_groups(self) -> list[QuickPhraseGroup]:
        with self._session() as s:
            rows = s.scalars(
                select(Frase).order_by(Frase.categoria, Frase.orden)
            ).all()
            phrases = [
                QuickPhrase(
                    id=r.id,
                    text=r.texto,
                    category=r.categoria,  # type: ignore[arg-type]
                    is_demo=r.es_demo,
                )
                for r in rows
            ]
            return _group_phrases(phrases)

    # ---- Vocabulario ----
    def list_signs(self) -> list[Sign]:
        with self._session() as s:
            return _sql_list_signs(s)

    def get_sign(self, label: str) -> Sign | None:
        with self._session() as s:
            row = s.scalar(
                select(Sena).where(Sena.etiqueta == label, Sena.activa.is_(True))
            )
            return _row_to_sign(row) if row else None

    # ---- Reconocimiento ----
    def add_report(
        self, user_id: int | None, data: RecognitionReportCreate
    ) -> RecognitionReport:
        with self._session() as s:
            row = ReporteReconocimiento(
                id=uuid.uuid4().hex[:12],
                usuario_id=user_id,
                texto_reconocido=data.recognized,
                texto_esperado=data.expected,
                confianza=data.confidence,
                modelo_version=data.model_version,
                comentario=data.comment,
                creado_en=_now(),
            )
            s.add(row)
            s.commit()
            return RecognitionReport(
                id=row.id, created_at=row.creado_en, **data.model_dump()
            )

    def list_models(self) -> list[RecognitionModel]:
        with self._session() as s:
            rows = s.scalars(
                select(ModeloReconocimiento).order_by(ModeloReconocimiento.creado_en.desc())
            ).all()
            return [
                RecognitionModel(
                    version=r.version,
                    architecture=r.arquitectura,
                    accuracy=r.exactitud,
                    num_classes=r.num_clases,
                    num_samples=r.num_muestras,
                    active=r.activo,
                    notes=r.notas,
                )
                for r in rows
            ]

    # ---- Dataset ----
    def add_sample(self, sample: DatasetSampleStored, consent: bool, notes: str) -> None:
        with self._session() as s:
            sena_id = s.scalar(select(Sena.id).where(Sena.etiqueta == sample.label))
            if sena_id is None:
                raise KeyError(sample.label)
            s.add(
                MuestraSena(
                    id=sample.id,
                    sena_id=sena_id,
                    archivo=sample.file,
                    consentimiento=consent,
                    validada=False,
                    frames=sample.frames,
                    duracion_ms=sample.duration_ms,
                    notas=notes,
                    creado_en=sample.created_at,
                )
            )
            s.commit()

    def dataset_summary(self) -> DatasetSummary:
        with self._session() as s:
            rows = s.execute(
                select(
                    Sena.etiqueta,
                    func.count(MuestraSena.id),
                    func.count(MuestraSena.id).filter(MuestraSena.validada.is_(True)),
                )
                .join(MuestraSena, MuestraSena.sena_id == Sena.id)
                .group_by(Sena.etiqueta)
            ).all()
            counts = {label: (int(n), int(v)) for label, n, v in rows}
            return _summary(_sql_list_signs(s), counts)



def _row_to_sign(r: Sena) -> Sign:
    return Sign(
        label=r.etiqueta,
        word=r.palabra,
        kind=r.tipo,  # type: ignore[arg-type]
        dynamic=r.tiene_movimiento,
        description=r.descripcion,
        region=r.region,
        validated=r.validada,
    )


def _sql_list_signs(s: Session) -> list[Sign]:
    rows = s.scalars(select(Sena).where(Sena.activa.is_(True)).order_by(Sena.id)).all()
    return [_row_to_sign(r) for r in rows]


def seed_database() -> None:
    """
    Inserta el catalogo de frases si esta vacio, las senas del vocabulario que
    falten y los modelos conocidos que falten. Lo existente no se modifica.

    NO crea usuarios: las cuentas se crean al registrarse.
    """
    with get_session() as s:
        if s.scalar(select(Frase).limit(1)) is None:
            for order, p in enumerate(_seed_phrases()):
                s.add(
                    Frase(
                        id=p.id,
                        texto=p.text,
                        categoria=p.category,
                        orden=order,
                        es_demo=p.is_demo,
                    )
                )
            s.commit()

        existing = set(s.scalars(select(Sena.etiqueta)).all())
        missing = [sg for sg in seed_signs() if sg.label not in existing]
        for sg in missing:
            s.add(
                Sena(
                    etiqueta=sg.label,
                    palabra=sg.word,
                    tipo=sg.kind,
                    tiene_movimiento=sg.dynamic,
                    descripcion=sg.description,
                    validada=False,
                    activa=True,
                    creado_en=_now(),
                )
            )

        versions = set(s.scalars(select(ModeloReconocimiento.version)).all())
        for m in SEED_MODELS:
            if m.version in versions:
                continue
            s.add(
                ModeloReconocimiento(
                    version=m.version,
                    arquitectura=m.architecture,
                    exactitud=m.accuracy,
                    num_clases=m.num_classes,
                    num_muestras=m.num_samples,
                    activo=m.active,
                    notas=m.notes,
                    creado_en=_now(),
                )
            )
        s.commit()
