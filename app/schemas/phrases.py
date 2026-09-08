"""Esquemas de las frases rapidas (FASE 7)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Category = Literal["saludos", "necesidades", "emergencias"]


class QuickPhrase(BaseModel):
    id: str
    text: str
    category: Category
    # true mientras la sena LSP asociada no este validada con personas
    # usuarias de LSP o interpretes.
    is_demo: bool = True


class QuickPhraseGroup(BaseModel):
    category: Category
    label: str
    phrases: list[QuickPhrase]
