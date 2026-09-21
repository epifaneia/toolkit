"""quote_verify — guard anti-alucinación de citas. DETERMINISTA, sin API.

El modelo devuelve, por cada evidencia, un `chunk_id` (elegido de una lista
cerrada, ver guardarrail_in) y una `quote`. Aquí se comprueba que la quote
EXISTE en el chunk citado (rapidfuzz partial_ratio ≥ min_ratio) y se deriva
la PÁGINA exacta del offset del match usando el `page_map` del chunk. El
modelo nunca escribe ubicaciones: la cita final la compone el código.

Contrato del chunk (lo produce el paso de limpieza):
    {"chunk_id": str, "doc": str, "section": str, "text": str,
     "page_start": int, "page_map": [{"offset": int, "page": int}, ...]}

Uso típico:
    from kit.guardarrail_out.quote_verify import verify_evidence, citation
    ok, why = verify_evidence(ev, chunk_by_id, min_ratio=0.85)
    if ok: print(citation(ok))          # [DOC p.81 §6.1] "quote..."
    else:  flags.append(f"quote_failed:{why}")

Regla: si un veredicto distinto de "abierto" se queda sin evidencia verificada,
el que llama lo DEGRADA al valor abierto y lo marca. Nunca se corrige la salida.

Extraído de CTSM s6_verify (9/9 contra ground truth, 0 flags).
"""
from __future__ import annotations

from rapidfuzz import fuzz


def page_of(chunk: dict, offset: int) -> int:
    """Página exacta de un offset dentro del chunk, según su page_map."""
    page = chunk["page_start"]
    for pm in chunk.get("page_map", []):
        if pm["offset"] <= offset:
            page = pm["page"]
    return page


def verify_evidence(ev: dict, chunk_by_id: dict, min_ratio: float = 0.85,
                    min_len: int = 10) -> tuple[dict | None, str | None]:
    """→ (evidencia verificada con página exacta, None) o (None, motivo)."""
    chunk = chunk_by_id.get(ev.get("chunk_id"))
    if chunk is None:
        return None, f"chunk inexistente: {ev.get('chunk_id')}"
    quote = (ev.get("quote") or "").strip()
    if len(quote) < min_len:
        return None, f"quote vacía/corta en {ev['chunk_id']}"
    aln = fuzz.partial_ratio_alignment(quote, chunk["text"])
    ratio = (aln.score if aln else 0.0) / 100.0
    if ratio < min_ratio:
        return None, f"quote no encontrada en {ev['chunk_id']} (ratio {ratio:.2f})"
    return {
        "chunk_id": chunk["chunk_id"],
        "doc": chunk["doc"],
        "section": chunk.get("section", ""),
        "page": page_of(chunk, aln.dest_start),
        "quote": quote,
        "match_ratio": round(ratio, 3),
    }, None


def citation(ev: dict) -> str:
    """La cita la compone el código: [DOC p.N §sección] "quote"."""
    sec = f" {ev['section']}" if ev.get("section") else ""
    return f'[{ev["doc"]} p.{ev["page"]}{sec}] "{ev["quote"]}"'


def seal(status: str, evidence: list[dict], chunk_by_id: dict, open_value: str,
         min_ratio: float = 0.85) -> tuple[str, list[dict], list[str]]:
    """Verifica todas las evidencias y degrada el status si ninguna sobrevive.

    → (status final, evidencias verificadas, flags)
    """
    verified, flags = [], []
    for ev in evidence or []:
        ok, why = verify_evidence(ev, chunk_by_id, min_ratio)
        if ok:
            verified.append(ok)
        else:
            flags.append(f"quote_failed:{why}")
    if status != open_value and not verified:
        flags.append(f"demoted:{status}->{open_value}")
        status = open_value
    return status, verified, flags
