"""motores — elegir el modelo por configuración, no por código.

    MOTOR=stub    python run.py     # sin red, sin claves (por defecto)
    MOTOR=ollama  python run.py     # local
    MOTOR=gemini  python run.py     # nube: el ledger lo registra como salida

El paso 4 recibe el objeto ya creado; cambiar de motor no toca ningún paso.
Los imports van dentro de cada rama: elegir `stub` no exige tener instalado
el SDK de nadie.
"""
from __future__ import annotations

import os

from .contrato import Modelo

NOMBRES = ("stub", "ollama", "gemini", "deep_research", "jev", "whisper", "kokoro")


def crear(nombre: str | None = None) -> Modelo:
    nombre = (nombre or os.environ.get("MOTOR", "").strip() or "stub").lower()
    if nombre == "stub":
        from .stub import Stub
        return Stub()
    if nombre == "ollama":
        from .ollama import Ollama
        return Ollama()
    if nombre == "gemini":
        from .gemini import Gemini
        return Gemini()
    if nombre == "deep_research":
        from .deep_research import DeepResearch
        return DeepResearch()
    if nombre == "jev":
        from .jev import Jev
        return Jev()
    if nombre == "whisper":
        from .whisper import Whisper
        return Whisper()
    if nombre == "kokoro":
        from .kokoro import Kokoro
        return Kokoro()
    raise ValueError(f"MOTOR desconocido: {nombre!r} ({' | '.join(NOMBRES)})")
