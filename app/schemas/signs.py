"""Esquemas del vocabulario de senas, el dataset y el reconocimiento."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

SignKind = Literal["palabra", "frase", "letra", "reposo"]

# Etiqueta del dataset: MAYUSCULAS, digitos y guion bajo (HOLA, HOLA_COMO_ESTAS, ENYE).
LABEL_PATTERN = r"^[A-Z0-9_]{1,40}$"


# --- Vocabulario ---


class Sign(BaseModel):
    label: str
    word: str
    kind: SignKind
    dynamic: bool
    description: str = ""
    region: str | None = None
    # false mientras ninguna persona usuaria de LSP o interprete la revise.
    validated: bool = False


# --- Reportes de reconocimiento ---


class RecognitionReportCreate(BaseModel):
    recognized: str = Field(max_length=200)
    expected: str = Field(default="", max_length=200)
    confidence: float | None = Field(default=None, ge=0, le=1)
    model_version: str | None = Field(default=None, max_length=40)
    comment: str = Field(default="", max_length=1000)


class RecognitionReport(RecognitionReportCreate):
    id: str
    created_at: datetime


class RecognitionModel(BaseModel):
    version: str
    architecture: str
    accuracy: float | None
    num_classes: int
    num_samples: int
    active: bool
    notes: str = ""


# --- Dataset ---
#
# Espejo de `ai/data/DATASET_FORMAT.md` (schemaVersion 1) y de
# `frontend/src/types/dataset.ts`. Se valida la forma de los landmarks para no
# guardar basura que despues rompa el entrenamiento.

Point = Annotated[list[float], Field(min_length=3, max_length=3)]
HandPoints = Annotated[list[Point], Field(min_length=21, max_length=21)]


class SampleHand(BaseModel):
    handedness: str = Field(max_length=10)
    score: float = 1.0
    landmarks: HandPoints
    worldLandmarks: HandPoints | None = None


class SampleFrame(BaseModel):
    t: float = Field(ge=0)
    hands: list[SampleHand] = Field(max_length=2)


class SampleCapture(BaseModel):
    fps: float = Field(gt=0, le=120)
    durationMs: float = Field(ge=0, le=15_000)
    frameCount: int = Field(ge=0)
    mirrored: bool
    model: str = Field(max_length=40)
    modelVersion: str = Field(max_length=40)
    handsMax: int = Field(ge=1, le=2)
    imageAspect: float = Field(gt=0, le=4)


class DatasetSampleIn(BaseModel):
    schemaVersion: Literal[1]
    label: str = Field(pattern=LABEL_PATTERN)
    word: str = Field(max_length=80)
    sampleId: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    createdAt: datetime
    source: str = Field(max_length=40)
    # Quien sube la muestra no puede marcarla como validada.
    validated: bool = False
    consent: bool
    notes: str = Field(default="", max_length=1000)
    capture: SampleCapture
    frames: list[SampleFrame] = Field(min_length=1, max_length=600)


class DatasetSampleStored(BaseModel):
    id: str
    label: str
    file: str
    frames: int
    duration_ms: int
    created_at: datetime


class DatasetLabelCount(BaseModel):
    label: str
    word: str
    samples: int
    validated_samples: int


class DatasetSummary(BaseModel):
    total: int
    labels: list[DatasetLabelCount]
