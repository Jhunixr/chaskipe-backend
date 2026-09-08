from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.services.store as store_module
from app.main import app
from app.services.store import use_memory_repository

API = "/api/v1"

# Cuenta de prueba: se registra en cada test sobre un repositorio limpio.
TEST_USER = {
    "name": "Andersson",
    "email": "andersson@example.pe",
    "password": "chaskipe-2026",
}


@pytest.fixture
def anon(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """
    Cliente SIN autenticar, contra el repositorio EN MEMORIA: rapido y sin
    necesidad de PostgreSQL. Se neutraliza el lifespan que intentaria
    conectar a la base de datos.
    """

    def _memory_only() -> str:
        use_memory_repository()
        return "memory"

    monkeypatch.setattr(store_module, "configure_repository", _memory_only)
    use_memory_repository()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client(anon: TestClient) -> TestClient:
    """Cliente ya autenticado: registra `TEST_USER` y fija el token."""
    res = anon.post(f"{API}/auth/register", json=TEST_USER)
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]
    anon.headers["Authorization"] = f"Bearer {token}"
    return anon
