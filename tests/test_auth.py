"""Pruebas de autenticacion y de aislamiento entre cuentas."""
from __future__ import annotations

import base64
import json

from fastapi.testclient import TestClient

from tests.conftest import TEST_USER

API = "/api/v1"

OTHER = {
    "name": "Maria",
    "email": "maria@example.pe",
    "password": "otra-clave-2026",
}

PROTECTED = [
    ("get", f"{API}/profile"),
    ("put", f"{API}/profile"),
    ("get", f"{API}/preferences"),
    ("put", f"{API}/preferences"),
    ("get", f"{API}/history"),
    ("post", f"{API}/history"),
    ("delete", f"{API}/history"),
    ("get", f"{API}/auth/me"),
]


# --------------------------------------------------------------- registro


def test_register_devuelve_token_y_usuario(anon: TestClient) -> None:
    r = anon.post(f"{API}/auth/register", json=TEST_USER)
    assert r.status_code == 201
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == TEST_USER["email"]
    assert body["user"]["id"] >= 1
    # La contrasena nunca viaja de vuelta.
    assert "password" not in str(body)


def test_register_correo_duplicado(anon: TestClient) -> None:
    assert anon.post(f"{API}/auth/register", json=TEST_USER).status_code == 201
    r = anon.post(f"{API}/auth/register", json=TEST_USER)
    assert r.status_code == 409


def test_register_correo_no_distingue_mayusculas(anon: TestClient) -> None:
    assert anon.post(f"{API}/auth/register", json=TEST_USER).status_code == 201
    r = anon.post(
        f"{API}/auth/register",
        json={**TEST_USER, "email": TEST_USER["email"].upper()},
    )
    assert r.status_code == 409


def test_register_contrasena_corta(anon: TestClient) -> None:
    r = anon.post(f"{API}/auth/register", json={**TEST_USER, "password": "corta"})
    assert r.status_code == 422


def test_register_correo_invalido(anon: TestClient) -> None:
    r = anon.post(f"{API}/auth/register", json={**TEST_USER, "email": "nope"})
    assert r.status_code == 422


# ------------------------------------------------------------------ login


def test_login_correcto(anon: TestClient) -> None:
    anon.post(f"{API}/auth/register", json=TEST_USER)
    r = anon.post(
        f"{API}/auth/login",
        json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
    )
    assert r.status_code == 200
    assert r.json()["user"]["name"] == TEST_USER["name"]


def test_login_contrasena_incorrecta(anon: TestClient) -> None:
    anon.post(f"{API}/auth/register", json=TEST_USER)
    r = anon.post(
        f"{API}/auth/login",
        json={"email": TEST_USER["email"], "password": "equivocada"},
    )
    assert r.status_code == 401


def test_login_correo_inexistente_mismo_mensaje(anon: TestClient) -> None:
    """No debe revelarse si un correo esta registrado o no."""
    anon.post(f"{API}/auth/register", json=TEST_USER)
    sin_cuenta = anon.post(
        f"{API}/auth/login", json={"email": "nadie@example.pe", "password": "x1234567"}
    )
    mala_clave = anon.post(
        f"{API}/auth/login",
        json={"email": TEST_USER["email"], "password": "equivocada"},
    )
    assert sin_cuenta.status_code == mala_clave.status_code == 401
    assert sin_cuenta.json()["detail"] == mala_clave.json()["detail"]


# ------------------------------------------------------------- proteccion


def test_endpoints_protegidos_sin_token(anon: TestClient) -> None:
    for method, url in PROTECTED:
        res = getattr(anon, method)(url)
        assert res.status_code == 401, f"{method.upper()} {url} devolvio {res.status_code}"


def test_token_invalido(anon: TestClient) -> None:
    anon.headers["Authorization"] = "Bearer no-es-un-token"
    assert anon.get(f"{API}/auth/me").status_code == 401


def test_token_con_payload_manipulado(anon: TestClient) -> None:
    """Cambiar el payload sin poder re-firmar debe invalidar el token."""
    token = anon.post(f"{API}/auth/register", json=TEST_USER).json()["access_token"]
    header, payload, signature = token.split(".")

    # Payload que apunta a otro usuario, con la firma original (que ya no cuadra).
    falso = base64.urlsafe_b64encode(json.dumps({"sub": "999"}).encode()).rstrip(b"=")
    anon.headers["Authorization"] = f"Bearer {header}.{falso.decode()}.{signature}"
    assert anon.get(f"{API}/auth/me").status_code == 401


def test_token_con_firma_invalida(anon: TestClient) -> None:
    token = anon.post(f"{API}/auth/register", json=TEST_USER).json()["access_token"]
    header, payload, _ = token.split(".")
    anon.headers["Authorization"] = f"Bearer {header}.{payload}.firma-inventada"
    assert anon.get(f"{API}/auth/me").status_code == 401


def test_me_devuelve_el_usuario(client: TestClient) -> None:
    r = client.get(f"{API}/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == TEST_USER["email"]


# ------------------------------------------------------------ aislamiento


def test_cada_cuenta_ve_solo_su_historial(anon: TestClient) -> None:
    a = anon.post(f"{API}/auth/register", json=TEST_USER).json()["access_token"]
    b = anon.post(f"{API}/auth/register", json=OTHER).json()["access_token"]

    anon.headers["Authorization"] = f"Bearer {a}"
    anon.post(f"{API}/history", json={"direction": "sign-to-text", "text": "de A"})

    anon.headers["Authorization"] = f"Bearer {b}"
    de_b = anon.get(f"{API}/history").json()
    assert de_b == [], "una cuenta no debe ver el historial de otra"

    anon.headers["Authorization"] = f"Bearer {a}"
    de_a = anon.get(f"{API}/history").json()
    assert [e["text"] for e in de_a] == ["de A"]


def test_no_se_puede_borrar_historial_ajeno(anon: TestClient) -> None:
    a = anon.post(f"{API}/auth/register", json=TEST_USER).json()["access_token"]
    b = anon.post(f"{API}/auth/register", json=OTHER).json()["access_token"]

    anon.headers["Authorization"] = f"Bearer {a}"
    entry_id = anon.post(
        f"{API}/history", json={"direction": "sign-to-text", "text": "de A"}
    ).json()["id"]

    # B conoce el id, pero no es suyo.
    anon.headers["Authorization"] = f"Bearer {b}"
    assert anon.delete(f"{API}/history/{entry_id}").status_code == 404

    # Sigue estando ahi para A.
    anon.headers["Authorization"] = f"Bearer {a}"
    assert len(anon.get(f"{API}/history").json()) == 1


def test_preferencias_son_por_cuenta(anon: TestClient) -> None:
    a = anon.post(f"{API}/auth/register", json=TEST_USER).json()["access_token"]
    b = anon.post(f"{API}/auth/register", json=OTHER).json()["access_token"]

    anon.headers["Authorization"] = f"Bearer {a}"
    anon.put(
        f"{API}/preferences",
        json={
            "theme": "oscuro",
            "text_size": "muy-grande",
            "voice_speed": "lenta",
            "avatar_speed": "rapida",
            "subtitles": False,
            "language": "es-MX",
        },
    )

    anon.headers["Authorization"] = f"Bearer {b}"
    assert anon.get(f"{API}/preferences").json()["theme"] == "sistema"

    anon.headers["Authorization"] = f"Bearer {a}"
    assert anon.get(f"{API}/preferences").json()["theme"] == "oscuro"


def test_perfil_no_puede_robar_correo_ajeno(anon: TestClient) -> None:
    anon.post(f"{API}/auth/register", json=TEST_USER)
    b = anon.post(f"{API}/auth/register", json=OTHER).json()["access_token"]

    anon.headers["Authorization"] = f"Bearer {b}"
    r = anon.put(
        f"{API}/profile", json={"name": "Maria", "email": TEST_USER["email"]}
    )
    assert r.status_code == 409
