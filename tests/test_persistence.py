"""
Pruebas de la capa de persistencia.

- La seleccion de repositorio y el fallback a memoria se prueban siempre.
- La integracion con PostgreSQL solo si hay una base de datos disponible
  (se salta en caso contrario).
"""
from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.db.base import init_engine
from app.schemas.history import HistoryEntryCreate
from app.schemas.preferences import Preferences
from app.services import store
from app.services.repository import EmailAlreadyUsed, MemoryRepository, SqlRepository

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
