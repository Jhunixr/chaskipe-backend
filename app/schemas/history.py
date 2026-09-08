"""Esquemas del historial de traducciones (FASE 7)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Direction = Literal["sign-to-text", "text-to-sign"]


class HistoryEntryCreate(BaseModel):
    direction: Direction
    text: str = Field(min_length=1, max_length=500)
    # true mientras la sena/equivalencia no este validada con LSP.
    is_demo: bool = True


class HistoryEntry(HistoryEntryCreate):
    id: str
    created_at: datetime
