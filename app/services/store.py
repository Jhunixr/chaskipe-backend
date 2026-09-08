"""
Seleccion del repositorio de datos (FASE 8).

Al arrancar la app (`app.main.lifespan`) se llama a `configure_repository()`:
- si PostgreSQL responde -> `SqlRepository` (crea tablas y semilla)
- si no -> `MemoryRepository` (fallback), avisado en /health

Los endpoints usan `get_repository()`.
"""
from __future__ import annotations

from app.core.config import settings
from app.db import base as db
from app.services.repository import (
    MemoryRepository,
    Repository,
    SqlRepository,
    seed_database,
)

_repository: Repository = MemoryRepository()
_backend: str = "memory"


def configure_repository() -> str:
    """
    Decide y prepara el repositorio. Devuelve 'postgresql' o 'memory'.
    """
    global _repository, _backend

    if db.init_engine():
        db.create_all()
        seed_database()
        _repository = SqlRepository()
        _backend = "postgresql"
    else:
        if settings.require_database:
            raise RuntimeError(
                "No se pudo conectar a la base de datos y "
                "CHASKIPE_REQUIRE_DATABASE=true."
            )
        _repository = MemoryRepository()
        _backend = "memory"

    return _backend


def get_repository() -> Repository:
    return _repository


def current_backend() -> str:
    return _backend


def use_memory_repository() -> None:
    """Fuerza el repositorio en memoria (para los tests)."""
    global _repository, _backend
    _repository = MemoryRepository()
    _backend = "memory"
