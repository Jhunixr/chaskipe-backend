"""Vocabulario, reportes de reconocimiento, modelos y dataset."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings

API = "/api/v1"


def _sample(label: str = "A", consent: bool = True, hands: bool = True) -> dict:
    hand = {
        "handedness": "Left",
        "score": 1,
        "landmarks": [[0.5, 0.5, 0.0]] * 21,
        "worldLandmarks": [[0.01, 0.02, 0.0]] * 21,
    }
    return {
        "schemaVersion": 1,
        "label": label,
        "word": label,
        "sampleId": "abc12345",
        "createdAt": "2026-10-07T12:00:00Z",
        "source": "web-collector",
        "validated": True,  # el servidor lo ignora
        "consent": consent,
        "notes": "prueba",
        "capture": {
            "fps": 30,
            "durationMs": 1000,
            "frameCount": 2,
            "mirrored": True,
            "model": "hand_landmarker",
            "modelVersion": "float16/latest",
            "handsMax": 2,
            "imageAspect": 0.75,
        },
        "frames": [
            {"t": 0, "hands": [hand] if hands else []},
            {"t": 33, "hands": [hand] if hands else []},
        ],
    }


@pytest.fixture(autouse=True)
def _tmp_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "dataset_dir", tmp_path / "dataset")
    return tmp_path / "dataset"


# --- Vocabulario ---


def test_signs_catalog(anon: TestClient) -> None:
    r = anon.get(f"{API}/signs")
    assert r.status_code == 200
    signs = {s["label"]: s for s in r.json()}
    # 6 palabras/frases + 27 letras
    assert len(signs) == 33
    assert signs["HOLA"]["dynamic"] is True
    assert signs["A"]["kind"] == "letra" and signs["A"]["dynamic"] is False
    assert signs["J"]["dynamic"] is True and signs["ENYE"]["dynamic"] is True
    assert all(s["validated"] is False for s in signs.values())


def test_get_sign(anon: TestClient) -> None:
    assert anon.get(f"{API}/signs/hola").json()["word"] == "Hola"
    assert anon.get(f"{API}/signs/NOEXISTE").status_code == 404


# --- Reconocimiento ---


def test_report_anonymous_and_authenticated(anon: TestClient) -> None:
    body = {"recognized": "M", "expected": "N", "confidence": 0.71, "model_version": "letras-v1"}
    r = anon.post(f"{API}/recognition/reports", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["expected"] == "N"


def test_report_invalid_token_is_401(anon: TestClient) -> None:
    r = anon.post(
        f"{API}/recognition/reports",
        json={"recognized": "A"},
        headers={"Authorization": "Bearer basura"},
    )
    assert r.status_code == 401


def test_report_validation(anon: TestClient) -> None:
    r = anon.post(f"{API}/recognition/reports", json={"recognized": "A", "confidence": 2})
    assert r.status_code == 422


def test_models(anon: TestClient) -> None:
    models = anon.get(f"{API}/recognition/models").json()
    assert any(m["version"] == "letras-v1" and m["num_classes"] == 24 for m in models)


# --- Dataset ---


def test_upload_requires_auth(anon: TestClient) -> None:
    assert anon.post(f"{API}/dataset/samples", json=_sample()).status_code == 401


def test_upload_and_summary(client: TestClient, _tmp_dataset: Path) -> None:
    r = client.post(f"{API}/dataset/samples", json=_sample("B"))
    assert r.status_code == 201, r.text
    stored = r.json()
    assert stored["label"] == "B" and stored["frames"] == 2

    path = _tmp_dataset / stored["file"]
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["validated"] is False  # el cliente no puede auto-validar
    assert saved["sampleId"] == stored["id"]
    assert path.parent.name == "B"

    summary = client.get(f"{API}/dataset/summary").json()
    counts = {c["label"]: c["samples"] for c in summary["labels"]}
    assert counts["B"] == 1 and counts["A"] == 0
    assert summary["total"] == 1


@pytest.mark.parametrize(
    "sample, detail",
    [
        (_sample(consent=False), "consentimiento"),
        (_sample(label="INVENTADA"), "vocabulario"),
        (_sample(hands=False), "ninguna mano"),
    ],
)
def test_upload_rejections(client: TestClient, sample: dict, detail: str) -> None:
    r = client.post(f"{API}/dataset/samples", json=sample)
    assert r.status_code == 422
    assert detail in r.text


def test_upload_rejects_bad_landmarks(client: TestClient) -> None:
    sample = _sample()
    sample["frames"][0]["hands"][0]["landmarks"] = [[0, 0, 0]] * 20
    assert client.post(f"{API}/dataset/samples", json=sample).status_code == 422


def test_upload_too_large(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_sample_bytes", 100)
    assert client.post(f"{API}/dataset/samples", json=_sample()).status_code == 413


def test_export_requires_admin_token(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    client.post(f"{API}/dataset/samples", json=_sample("C"))
    # sin token configurado: desactivado
    assert client.get(f"{API}/dataset/export").status_code == 403

    monkeypatch.setattr(settings, "admin_token", "secreto-admin")
    assert client.get(f"{API}/dataset/export", headers={"X-Admin-Token": "otro"}).status_code == 403
    r = client.get(f"{API}/dataset/export", headers={"X-Admin-Token": "secreto-admin"})
    assert r.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert len(names) == 1 and names[0].startswith("C/C__")
