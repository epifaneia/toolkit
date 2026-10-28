"""Paso 2 · Contexto. Código: qué trozos verá el modelo para esta pregunta."""
from __future__ import annotations

from kit.contexto.retrieve import Retriever

TOP_K = 3


def recuperar(art: dict) -> dict:
    """→ {"pregunta", "chunks"} con solo los TOP_K trozos más afines (BM25, sin red)."""
    por_id = {c["chunk_id"]: c for c in art["chunks"]}
    candidatos = Retriever(art["chunks"], max_chars=0).candidates(art["pregunta"], top_k=TOP_K)
    return {"pregunta": art["pregunta"], "chunks": [por_id[c["chunk_id"]] for c in candidatos]}
