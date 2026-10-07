"""
Vocabulario semilla de senas y modelos de reconocimiento conocidos.

Espejo de `SIGN_VOCAB` (`frontend/src/types/dataset.ts`). Al arrancar se
insertan las etiquetas que falten en la tabla `senas`; las que ya existen no
se tocan, para no pisar lo que el equipo haya editado (p. ej. `validada`).

Ninguna sena sale validada: eso solo lo decide una revision con personas
usuarias de LSP o interpretes.
"""
from __future__ import annotations

from app.schemas.signs import RecognitionModel, Sign

_WORDS: list[tuple[str, str, str, bool, str]] = [
    # (etiqueta, palabra, tipo, movimiento, descripcion)
    ("HOLA", "Hola", "palabra", True, "Saludo."),
    ("GRACIAS", "Gracias", "palabra", True, ""),
    ("ADIOS", "Adios", "palabra", True, ""),
    ("HOLA_COMO_ESTAS", "Hola, como estas", "frase", True, ""),
    ("CUIDATE", "Cuidate", "palabra", True, ""),
    (
        "REPOSO",
        "Reposo (sin sena)",
        "reposo",
        False,
        "Mano(s) en el encuadre sin hacer ninguna sena: evita falsos positivos.",
    ),
]

# Abecedario dactilologico. J, Z y la enye llevan movimiento.
_DYNAMIC_LETTERS = {"J", "Z", "ENYE"}
_LETTERS = list("ABCDEFGHIJKLMN") + ["ENYE"] + list("OPQRSTUVWXYZ")


def seed_signs() -> list[Sign]:
    signs = [
        Sign(label=label, word=word, kind=kind, dynamic=dynamic, description=desc)  # type: ignore[arg-type]
        for label, word, kind, dynamic, desc in _WORDS
    ]
    for letter in _LETTERS:
        dynamic = letter in _DYNAMIC_LETTERS
        signs.append(
            Sign(
                label=letter,
                word="N (enye)" if letter == "ENYE" else letter,
                kind="letra",
                dynamic=dynamic,
                description=(
                    "Letra con movimiento." if dynamic else "Letra estatica (pose fija)."
                ),
            )
        )
    return signs


# Modelos ya entrenados que la app trae de serie. Ver ai/README.md.
SEED_MODELS: list[RecognitionModel] = [
    RecognitionModel(
        version="letras-v1",
        architecture="mlp-73-128-64-24 (pose estatica, world landmarks)",
        accuracy=0.921,
        num_classes=24,
        num_samples=3575,
        active=True,
        notes=(
            "Abecedario estatico de la LSP. Dataset publico 'Static Hand Gestures "
            "of the Peruvian Sign Language Alphabet' (CC BY-SA 4.0). Una sola "
            "mano de referencia; M, N y Q son las letras mas debiles."
        ),
    ),
]
