"""Pruebas de la API."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.repository import CATEGORY_ORDER

API = "/api/v1"


def _add(client: TestClient, text: str, direction: str = "sign-to-text") -> str:
    r = client.post(f"{API}/history", json={"direction": direction, "text": text})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_health(anon: TestClient) -> None:
    r = anon.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["persistence"] == "memory"


def test_get_profile(client: TestClient) -> None:
    r = client.get(f"{API}/profile")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"name", "email"}


def test_update_profile(client: TestClient) -> None:
    r = client.put(
        f"{API}/profile", json={"name": "Maria", "email": "maria@example.pe"}
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Maria"
    # persiste dentro de la misma sesion de proceso
    assert client.get(f"{API}/profile").json()["name"] == "Maria"


def test_update_profile_invalid(client: TestClient) -> None:
    assert (
        client.put(
            f"{API}/profile", json={"name": "", "email": "no-es-email"}
        ).status_code
        == 422
    )


def test_history_empieza_vacio(client: TestClient) -> None:
    """El historial pertenece a la cuenta: una cuenta nueva no tiene nada."""
    r = client.get(f"{API}/history")
    assert r.status_code == 200
    assert r.json() == []


def test_history_order(client: TestClient) -> None:
    for text in ("uno", "dos", "tres"):
        _add(client, text)
    times = [e["created_at"] for e in client.get(f"{API}/history").json()]
    assert times == sorted(times, reverse=True)


def test_history_create_and_delete(client: TestClient) -> None:
    entry_id = _add(client, "Necesito ayuda")
    assert len(client.get(f"{API}/history").json()) == 1

    assert client.delete(f"{API}/history/{entry_id}").status_code == 204
    assert client.get(f"{API}/history").json() == []


def test_history_delete_missing(client: TestClient) -> None:
    assert client.delete(f"{API}/history/nope").status_code == 404


def test_history_limit(client: TestClient) -> None:
    for text in ("uno", "dos", "tres"):
        _add(client, text)
    assert len(client.get(f"{API}/history", params={"limit": 2}).json()) == 2


def test_history_clear(client: TestClient) -> None:
    for text in ("uno", "dos"):
        _add(client, text)
    r = client.delete(f"{API}/history")
    assert r.status_code == 200
    assert r.json()["deleted"] == 2
    assert client.get(f"{API}/history").json() == []


def test_history_invalid_direction(client: TestClient) -> None:
    r = client.post(f"{API}/history", json={"direction": "otra", "text": "x"})
    assert r.status_code == 422


def test_phrases_es_publico(anon: TestClient) -> None:
    """El catalogo de frases no requiere cuenta."""
    r = anon.get(f"{API}/phrases")
    assert r.status_code == 200
    groups = r.json()
    assert [g["category"] for g in groups] == CATEGORY_ORDER
    all_phrases = [p for g in groups for p in g["phrases"]]
    assert all(p["is_demo"] for p in all_phrases)
    assert any(p["text"] == "Necesito ayuda" for p in all_phrases)
    assert len(all_phrases) >= 50
    assert len({p["id"] for p in all_phrases}) == len(all_phrases)


def test_cors_headers(client: TestClient) -> None:
    r = client.get(f"{API}/profile", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
