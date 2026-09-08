"""Endpoints de las frases rapidas (FASE 8)."""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.phrases import QuickPhraseGroup
from app.services.store import get_repository

router = APIRouter(prefix="/phrases", tags=["phrases"])


@router.get("", response_model=list[QuickPhraseGroup])
def list_phrase_groups() -> list[QuickPhraseGroup]:
    """
    Frases rapidas agrupadas por categoria.

    Nota: las senas LSP asociadas a estas frases NO estan validadas con
    personas usuarias de LSP ni interpretes (`is_demo=true`).
    """
    return get_repository().list_phrase_groups()
