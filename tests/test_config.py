"""Configuracion: URL de la base de datos y comprobaciones de produccion."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings, normalize_database_url


@pytest.mark.parametrize(
    "url, expected",
    [
        # Formato de Dokploy / Heroku / Railway
        ("postgresql://u:p@chaskipe-db:5432/chaskipe", "postgresql+psycopg://u:p@chaskipe-db:5432/chaskipe"),
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("  postgresql://u:p@host/db  ", "postgresql+psycopg://u:p@host/db"),
        # Ya correcta: no se toca
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("", ""),
    ],
)
def test_normalize_database_url(url: str, expected: str) -> None:
    assert normalize_database_url(url) == expected


def test_settings_normalize_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHASKIPE_DATABASE_URL", "postgresql://a:b@db:5432/x")
    assert Settings(_env_file=None).database_url == "postgresql+psycopg://a:b@db:5432/x"


def test_development_generates_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHASKIPE_SECRET_KEY", raising=False)
    s = Settings(_env_file=None, environment="development")
    assert len(s.secret_key) >= 32
    assert s.require_database is False


def test_production_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHASKIPE_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None, environment="production")


def test_production_requires_database_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    s = Settings(_env_file=None, environment="production", secret_key="x" * 40)
    assert s.require_database is True
    # se puede desactivar explicitamente
    s = Settings(_env_file=None, environment="production", secret_key="x" * 40, require_database=False)
    assert s.require_database is False
