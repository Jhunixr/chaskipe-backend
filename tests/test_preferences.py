"""Tests de las preferencias de accesibilidad."""
from __future__ import annotations

from fastapi.testclient import TestClient

VALID = {
    "theme": "oscuro",
    "text_size": "muy-grande",
    "voice_speed": "lenta",
    "avatar_speed": "rapida",
    "subtitles": False,
    "language": "es-MX",
}


def test_get_devuelve_valores_por_defecto(client: TestClient) -> None:
    body = client.get("/api/v1/preferences").json()
    assert body == {
        "theme": "sistema",
        "text_size": "normal",
        "voice_speed": "normal",
        "avatar_speed": "normal",
        "subtitles": True,
        "language": "es-PE",
    }


def test_put_guarda_y_get_lo_devuelve(client: TestClient) -> None:
    res = client.put("/api/v1/preferences", json=VALID)
    assert res.status_code == 200
    assert res.json() == VALID
    # La lectura posterior refleja lo guardado.
    assert client.get("/api/v1/preferences").json() == VALID


def test_rechaza_tema_invalido(client: TestClient) -> None:
    res = client.put("/api/v1/preferences", json={**VALID, "theme": "morado"})
    assert res.status_code == 422


def test_rechaza_velocidad_invalida(client: TestClient) -> None:
    res = client.put(
        "/api/v1/preferences", json={**VALID, "voice_speed": "supersonica"}
    )
    assert res.status_code == 422


def test_campos_ausentes_toman_el_valor_por_defecto(client: TestClient) -> None:
    """Un cuerpo parcial es valido: lo que falta usa el valor por defecto."""
    res = client.put("/api/v1/preferences", json={"theme": "claro"})
    assert res.status_code == 200
    body = res.json()
    assert body["theme"] == "claro"
    assert body["text_size"] == "normal"
    assert body["subtitles"] is True
