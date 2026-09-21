"""retrieve — qué ve el modelo por cada ítem. Paso 2, determinista, sin API.

Dado un corpus de chunks (los que produce el paso de limpieza: cada uno con
`chunk_id`, `text` y sus metadatos) y una consulta (el texto del requisito, la
pregunta, el mensaje), devuelve los chunks candidatos que el modelo podrá citar.

Dos modos, elegidos por tamaño:
  · PASSTHROUGH: si el corpus entero cabe en el contexto del modelo
    (`max_chars`), va entero. No hay recuperación que perder.
  · BM25 top-K: si no cabe, ranking léxico por consulta. Sin embeddings, sin
    red, reproducible. En un manual de 1.136 páginas bastó top-10 (recall 9/9
    en top-4).

La salida es siempre una lista de candidatos con id: el paso siguiente
(guardarrail_in) los convierte en el enum cerrado que el modelo puede citar.

Uso:
    from kit.contexto.retrieve import Retriever
    r = Retriever(chunks, max_chars=900_000)
    for req in requisitos:
        cand = r.candidates(req["text"], top_k=10)   # [{"chunk_id", "score", ...}]
"""
from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class Retriever:
    def __init__(self, chunks: list[dict], max_chars: int = 0, text_key: str = "text"):
        """`max_chars` = 0 desactiva el passthrough (siempre BM25)."""
        self.chunks = chunks
        self.text_key = text_key
        self.total_chars = sum(len(c.get(text_key, "")) for c in chunks)
        self.passthrough = bool(max_chars) and self.total_chars <= max_chars
        self._bm25 = None
        if not self.passthrough and chunks:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi([tokens(c.get(text_key, "")) for c in chunks])

    @property
    def mode(self) -> str:
        return "passthrough" if self.passthrough else "bm25"

    def candidates(self, query: str, top_k: int = 10,
                   keep: tuple[str, ...] = ("chunk_id", "doc", "section", "page_start", "page_end")) -> list[dict]:
        """Candidatos para una consulta, con `score` y los metadatos de `keep`."""
        if self.passthrough or self._bm25 is None:
            idx, scores = list(range(len(self.chunks))), [0.0] * len(self.chunks)
        else:
            all_scores = self._bm25.get_scores(tokens(query))
            idx = sorted(range(len(self.chunks)), key=lambda i: -all_scores[i])[:top_k]
            scores = [float(all_scores[i]) for i in idx]
        out = []
        for i, s in zip(idx, scores):
            c = self.chunks[i]
            row = {k: c[k] for k in keep if k in c}
            row["score"] = round(s, 2)
            out.append(row)
        return out
