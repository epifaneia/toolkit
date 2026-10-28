"""Paso 1 · Limpieza. Código: del documento en bruto a trozos con id."""
from __future__ import annotations

from pathlib import Path


def limpiar(entrada: dict) -> dict:
    """{"documento": ruta, "pregunta": str} → {"pregunta", "chunks": [{"chunk_id", "text"}]}"""
    bruto = Path(entrada["documento"]).read_text(encoding="utf-8")
    parrafos = [" ".join(p.split()) for p in bruto.split("\n\n") if p.strip()]
    chunks = [{"chunk_id": f"p{n}", "text": p} for n, p in enumerate(parrafos, 1)]
    return {"pregunta": entrada["pregunta"], "chunks": chunks}
