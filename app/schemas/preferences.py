"""Esquemas de las preferencias de accesibilidad."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TextSize = Literal["normal", "grande", "muy-grande"]
Speed = Literal["lenta", "normal", "rapida"]
Theme = Literal["claro", "oscuro", "sistema"]


class Preferences(BaseModel):
    """
    Preferencias de accesibilidad de la persona usuaria.

    Todas se aplican de verdad en el frontend; `theme` y `text_size` afectan a
    toda la app, `voice_speed` a la sintesis de voz y `avatar_speed` al avatar.
    """

    theme: Theme = "sistema"
    text_size: TextSize = "normal"
    voice_speed: Speed = "normal"
    avatar_speed: Speed = "normal"
    subtitles: bool = True
    language: str = Field(default="es-PE", min_length=2, max_length=10)


class PreferencesUpdate(Preferences):
    """Cuerpo de PUT /preferences."""
