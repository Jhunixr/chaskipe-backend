"""Modelos ORM y motor de base de datos (FASE 8)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Tablas (esquema de la FASE 8) ---


class Usuario(Base):
    """Cuenta de una persona usuaria. La contrasena se guarda hasheada."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80))
    correo: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    contrasena_hash: Mapped[str] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class PreferenciaAccesibilidad(Base):
    """Preferencias de accesibilidad de un usuario (una fila por usuario)."""

    __tablename__ = "preferencias_accesibilidad"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), unique=True, index=True
    )
    tema: Mapped[str] = mapped_column(String(10), default="sistema")
    tamano_texto: Mapped[str] = mapped_column(String(12), default="normal")
    velocidad_voz: Mapped[str] = mapped_column(String(10), default="normal")
    velocidad_avatar: Mapped[str] = mapped_column(String(10), default="normal")
    subtitulos: Mapped[bool] = mapped_column(Boolean, default=True)
    idioma: Mapped[str] = mapped_column(String(10), default="es-PE")


class Frase(Base):
    """Frase rapida. Las senas LSP asociadas NO estan validadas (`es_demo`)."""

    __tablename__ = "frases"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    texto: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(20), index=True)
    orden: Mapped[int] = mapped_column(default=0)
    es_demo: Mapped[bool] = mapped_column(default=True)


class HistorialTraduccion(Base):
    """Traduccion guardada. Pertenece a un usuario."""

    __tablename__ = "historial_traduccion"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    direccion: Mapped[str] = mapped_column(String(20))  # sign-to-text | text-to-sign
    texto: Mapped[str] = mapped_column(String(500))
    es_demo: Mapped[bool] = mapped_column(default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


# --- Vocabulario de senas (FASE 11) ---
#
# Hasta ahora el vocabulario vivia en el codigo (SIGN_VOCAB en TypeScript y
# las carpetas de ai/data/raw/). Eso obliga a recompilar la app para agregar
# una sena. Aqui pasa a ser dato: la app puede pedir el vocabulario vigente y
# el equipo de LSP puede ampliarlo sin tocar codigo.


class Sena(Base):
    """
    Una sena del vocabulario de LSP.

    `validada` es el campo central del proyecto: mientras sea False, la app
    debe mostrar la sena como DEMO. Ninguna sena se considera correcta hasta
    que una persona usuaria de LSP o interprete la revisa.
    """

    __tablename__ = "senas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Etiqueta del dataset: MAYUSCULAS, sin tildes (HOLA, GRACIAS, REPOSO).
    etiqueta: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    palabra: Mapped[str] = mapped_column(String(80))
    # Que tipo de sena es, porque cambia como se captura y se reconoce.
    tipo: Mapped[str] = mapped_column(String(20), default="palabra")
    # true si la sena tiene movimiento (se graba una secuencia, no una pose).
    tiene_movimiento: Mapped[bool] = mapped_column(default=False)
    descripcion: Mapped[str] = mapped_column(Text, default="")
    # Variacion regional: la LSP no es uniforme en todo el Peru.
    region: Mapped[str | None] = mapped_column(String(60), nullable=True)
    validada: Mapped[bool] = mapped_column(default=False, index=True)
    validada_por: Mapped[str | None] = mapped_column(String(120), nullable=True)
    validada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activa: Mapped[bool] = mapped_column(default=True, index=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    muestras: Mapped[list["MuestraSena"]] = relationship(
        back_populates="sena", cascade="all, delete-orphan"
    )


class MuestraSena(Base):
    """
    Registro de una grabacion del dataset. **No guarda los landmarks**: esos
    viven en ai/data/ como archivos JSON, porque son miles de numeros por
    muestra y la base de datos no es el lugar para un dataset de entrenamiento.

    Esta tabla existe para saber que se grabo, quien lo consintio y si ya se
    reviso, sin tener que leer el disco.
    """

    __tablename__ = "muestras_sena"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    sena_id: Mapped[int] = mapped_column(
        ForeignKey("senas.id", ondelete="CASCADE"), index=True
    )
    # Ruta relativa dentro de ai/data/. La fuente de verdad sigue siendo el archivo.
    archivo: Mapped[str] = mapped_column(String(255))
    # Sin consentimiento explicito la muestra no se usa. Nunca por defecto.
    consentimiento: Mapped[bool] = mapped_column(default=False)
    validada: Mapped[bool] = mapped_column(default=False, index=True)
    frames: Mapped[int] = mapped_column(default=0)
    duracion_ms: Mapped[int] = mapped_column(default=0)
    notas: Mapped[str] = mapped_column(Text, default="")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    sena: Mapped["Sena"] = relationship(back_populates="muestras")


class ModeloReconocimiento(Base):
    """
    Version de un modelo entrenado. Permite saber que modelo produjo cada
    reconocimiento y volver a una version anterior si una nueva empeora.
    """

    __tablename__ = "modelos_reconocimiento"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    arquitectura: Mapped[str] = mapped_column(String(60), default="mlp")
    # Metricas del entrenamiento, para comparar versiones.
    exactitud: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_clases: Mapped[int] = mapped_column(default=0)
    num_muestras: Mapped[int] = mapped_column(default=0)
    # Solo un modelo activo a la vez: es el que la app descarga.
    activo: Mapped[bool] = mapped_column(default=False, index=True)
    notas: Mapped[str] = mapped_column(Text, default="")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class ReporteReconocimiento(Base):
    """
    Aviso de que un reconocimiento salio mal, enviado desde la app.

    Es el circuito de mejora del proyecto: sin esto no hay forma de saber que
    senas falla el modelo en uso real. No guarda video ni landmarks.
    """

    __tablename__ = "reportes_reconocimiento"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    # Anonimo si la persona no tiene sesion: el reporte importa mas que saber quien.
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    texto_reconocido: Mapped[str] = mapped_column(String(200), default="")
    texto_esperado: Mapped[str] = mapped_column(String(200), default="")
    confianza: Mapped[float | None] = mapped_column(Float, nullable=True)
    modelo_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    comentario: Mapped[str] = mapped_column(Text, default="")
    revisado: Mapped[bool] = mapped_column(default=False, index=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


# --- Motor y sesiones ---

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def init_engine() -> bool:
    """
    Crea el engine y verifica la conexion. Devuelve True si PostgreSQL
    responde; False si hay que caer a memoria.
    """
    global _engine, _SessionLocal

    url = settings.database_url.strip()
    if not url:
        return False

    try:
        _engine = create_engine(url, pool_pre_ping=True, future=True)
        with _engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        _SessionLocal = sessionmaker(
            bind=_engine, autoflush=False, expire_on_commit=False
        )
        return True
    except Exception:
        _engine = None
        _SessionLocal = None
        return False


def create_all() -> None:
    """Crea las tablas si no existen (para desarrollo / tests sin Alembic)."""
    if _engine is not None:
        Base.metadata.create_all(_engine)


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("La base de datos no esta inicializada")
    return _SessionLocal()
