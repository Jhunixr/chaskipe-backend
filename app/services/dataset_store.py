"""
Almacen de muestras del dataset subidas desde la app.

Cada muestra se guarda como un archivo JSON, con el mismo nombre y formato
que `ai/data/raw/<ETIQUETA>/` (ver `ai/data/DATASET_FORMAT.md`), dentro de
`settings.dataset_dir`. La base de datos solo guarda el registro (que se
grabo, cuando y con que consentimiento): el dataset no vive en PostgreSQL.

Para entrenar: `GET /api/v1/dataset/export` (zip) y descomprimir en
`ai/data/raw/`.
"""
from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.schemas.signs import DatasetSampleIn, DatasetSampleStored


def _root() -> Path:
    return Path(settings.dataset_dir)


def save_sample(sample: DatasetSampleIn) -> DatasetSampleStored:
    """Escribe la muestra en disco y devuelve su registro."""
    now = datetime.now(timezone.utc)
    sample_id = uuid.uuid4().hex[:12]
    stamp = now.strftime("%Y-%m-%dT%H-%M-%S")
    rel = Path(sample.label) / f"{sample.label}__{stamp}__{sample_id}.json"

    data = sample.model_dump(mode="json")
    data["sampleId"] = sample_id
    data["validated"] = False  # solo una revision con LSP lo cambia
    data["source"] = "api-upload"

    path = _root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)  # sin archivos a medias si el proceso muere

    return DatasetSampleStored(
        id=sample_id,
        label=sample.label,
        file=rel.as_posix(),
        frames=len(sample.frames),
        duration_ms=int(sample.capture.durationMs),
        created_at=now,
    )


def discard_sample(stored: DatasetSampleStored) -> None:
    """Borra el archivo si el registro en la base de datos fallo."""
    (_root() / stored.file).unlink(missing_ok=True)


def export_zip() -> bytes:
    """Todas las muestras en un zip con la estructura de `ai/data/raw/`."""
    buf = io.BytesIO()
    root = _root()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if root.exists():
            for path in sorted(root.rglob("*.json")):
                zf.write(path, path.relative_to(root).as_posix())
    return buf.getvalue()
