"""
Pruebas de la capa de persistencia.

- La seleccion de repositorio y el fallback a memoria se prueban siempre.
- La integracion con PostgreSQL solo si hay una base de datos disponible
  (se salta en caso contrario).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.db.base import init_engine
from app.schemas.history import HistoryEntryCreate
from app.schemas.preferences import Preferences
from app.services import store
from app.schemas.signs import DatasetSampleStored, RecognitionReportCreate
from app.services.repository import (
    EmailAlreadyUsed,
    MemoryRepository,
    SqlRepository,
    seed_database,
)

_DB_AVAILABLE = init_engine()


def test_fallback_to_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si la BD no conecta, se usa MemoryRepository y no se lanza excepcion."""
    monkeypatch.setattr(store.db, "init_engine", lambda: False)
    monkeypatch.setattr(settings, "require_database", False)
    backend = store.configure_repository()
    assert backend == "memory"
    assert isinstance(store.get_repository(), MemoryRepository)


def test_require_database_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store.db, "init_engine", lambda: False)
    monkeypatch.setattr(settings, "require_database", True)
    with pytest.raises(RuntimeError):
        store.configure_repository()


@pytest.mark.skipif(not _DB_AVAILABLE, reason="PostgreSQL no disponible")
def test_sql_repository_roundtrip() -> None:
    store.configure_repository()
    assert store.current_backend() == "postgresql"
    repo = SqlRepository()

    # Correo unico por ejecucion: el test no deja basura reutilizable.
    email = f"pg-{uuid.uuid4().hex[:8]}@test.pe"
    user = repo.create_user("Test PG", email, "clave-de-prueba")
    assert user.id >= 1

    # autenticacion
    assert repo.authenticate(email, "clave-de-prueba") is not None
    assert repo.authenticate(email, "equivocada") is None
    assert repo.get_user(user.id) is not None

    # correo duplicado
    with pytest.raises(EmailAlreadyUsed):
        repo.create_user("Otro", email, "otra-clave-1234")

    # perfil
    repo.update_profile(user.id, "Renombrado", email)
    assert repo.get_profile(user.id).name == "Renombrado"

    # preferencias (creadas al registrarse, por usuario)
    assert repo.get_preferences(user.id).theme == "sistema"
    repo.update_preferences(user.id, Preferences(theme="oscuro"))
    assert repo.get_preferences(user.id).theme == "oscuro"

    # historial: crear, listar, borrar
    entry = repo.add_history(
        user.id,
        HistoryEntryCreate(direction="sign-to-text", text="Prueba integracion"),
    )
    assert entry.id in [e.id for e in repo.list_history(user.id)]
    assert repo.delete_history(user.id, entry.id) is True
    assert repo.delete_history(user.id, entry.id) is False

    # frases (catalogo compartido)
    groups = repo.list_phrase_groups()
    assert [g.category for g in groups] == [
        "saludos",
        "necesidades",
        "emergencias",
    ]


@pytest.mark.skipif(not _DB_AVAILABLE, reason="PostgreSQL no disponible")
def test_sql_aislamiento_entre_cuentas() -> None:
    """Una cuenta no ve ni puede borrar el historial de otra."""
    store.configure_repository()
    repo = SqlRepository()

    a = repo.create_user("A", f"a-{uuid.uuid4().hex[:8]}@test.pe", "clave-a-1234")
    b = repo.create_user("B", f"b-{uuid.uuid4().hex[:8]}@test.pe", "clave-b-1234")

    entry = repo.add_history(
        a.id, HistoryEntryCreate(direction="sign-to-text", text="solo de A")
    )

    assert entry.id not in [e.id for e in repo.list_history(b.id)]
    assert repo.delete_history(b.id, entry.id) is False
    assert repo.delete_history(a.id, entry.id) is True


@pytest.mark.skipif(not _DB_AVAILABLE, reason="PostgreSQL no disponible")
def test_sql_vocabulario_reportes_y_dataset() -> None:
    """Senas sembradas, reportes, modelos y registro de muestras en PostgreSQL."""
    store.configure_repository()
    repo = SqlRepository()

    labels = [s.label for s in repo.list_signs()]
    assert {"HOLA", "REPOSO", "A", "ENYE", "Z"} <= set(labels)
    assert repo.get_sign("NOEXISTE") is None

    # sembrar dos veces no duplica
    seed_database()
    assert len(repo.list_signs()) == len(labels)

    report = repo.add_report(None, RecognitionReportCreate(recognized="M", expected="N"))
    assert report.id

    assert any(m.version == "letras-v1" for m in repo.list_models())

    before = {c.label: c.samples for c in repo.dataset_summary().labels}
    sample = DatasetSampleStored(
        id=uuid.uuid4().hex[:12],
        label="Q",
        file="Q/Q__prueba.json",
        frames=10,
        duration_ms=500,
        created_at=datetime.now(timezone.utc),
    )
    repo.add_sample(sample, consent=True, notes="test")
    after = {c.label: c.samples for c in repo.dataset_summary().labels}
    assert after["Q"] == before["Q"] + 1
