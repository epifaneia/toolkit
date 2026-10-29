"""quote_verify — guard anti-alucinación de citas. DETERMINISTA, sin API.

El modelo devuelve, por cada evidencia, un `chunk_id` (elegido de una lista
cerrada, ver guardarrail_in) y una `quote`. Aquí se comprueba que la quote
EXISTE en el chunk citado y se deriva la PÁGINA exacta del offset del match
usando el `page_map` del chunk. El modelo nunca escribe ubicaciones: la cita
final la compone el código.

  · Literal tras normalizar el ruido tipográfico (kit.limpieza.text_norm): sin
    umbral, o está o no está.
  · Si no es literal pero se parece (rapidfuzz partial_ratio ≥ min_ratio), solo
    se acepta si dice lo MISMO: las mismas cifras y las mismas negaciones. Un
    parecido del 96 % no distingue «debe» de «no debe», ni «3 a 25» de «4 a 16».
    Si pasa, se marca `literal: False` y se guarda aparte lo que escribió el
    modelo (`quote_modelo`).
  · La cita devuelta es SIEMPRE el texto del documento, nunca el del modelo.

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

import re

from rapidfuzz import fuzz

from kit.limpieza.text_norm import find_literal_span

_CIFRA = re.compile(r"\d+")
_NEGACION = re.compile(r"\b(?:no|not|never|nunca|ni|sin|without|cannot|neither|nor|none|nothing|nada|ningún|ninguna|ninguno|jamás)\b|n't\b",
                       re.IGNORECASE)


def page_of(chunk: dict, offset: int) -> int:
    """Página exacta de un offset dentro del chunk, según su page_map."""
    page = chunk["page_start"]
    for pm in chunk.get("page_map", []):
        if pm["offset"] <= offset:
            page = pm["page"]
    return page


def _como_se_lee(tramo: str) -> str:
    """El tramo del documento como lo lee una persona: palabras partidas a final de línea
    recompuestas y el espacio en blanco colapsado. No cambia ni una letra."""
    return " ".join(re.sub(r"(\w)-[ \t]*\r?\n\s*(\w)", r"\1\2", tramo).split())


def _a_palabras(texto: str, ini: int, fin: int) -> tuple[int, int]:
    """El alineamiento de rapidfuzz corta a media palabra: se ensancha a palabras enteras."""
    while ini > 0 and not texto[ini - 1].isspace():
        ini -= 1
    while fin < len(texto) and not texto[fin].isspace():
        fin += 1
    return ini, fin


def mismo_sentido(quote: str, tramo: str) -> str | None:
    """None si la paráfrasis conserva cifras y negaciones; si no, el motivo.

    Las cifras se comparan como multiconjunto de números («3.6» y «3,6» dan lo mismo);
    las negaciones, por recuento. Es una comprobación barata y determinista: no
    entiende el texto, pero caza los dos cambios que más daño hacen en una cita.
    """
    if sorted(_CIFRA.findall(quote)) != sorted(_CIFRA.findall(tramo)):
        return f"cifras distintas: modelo {_CIFRA.findall(quote)} / documento {_CIFRA.findall(tramo)}"
    if len(_NEGACION.findall(quote)) != len(_NEGACION.findall(tramo)):
        return "negación distinta entre la cita del modelo y el documento"
    return None


def verify_evidence(ev: dict, chunk_by_id: dict, min_ratio: float = 0.85,
                    min_len: int = 10) -> tuple[dict | None, str | None]:
    """→ (evidencia verificada con página exacta, None) o (None, motivo)."""
    chunk = chunk_by_id.get(ev.get("chunk_id"))
    if chunk is None:
        return None, f"chunk inexistente: {ev.get('chunk_id')}"
    quote = (ev.get("quote") or "").strip()
    if len(quote) < min_len:
        return None, f"quote vacía/corta en {ev['chunk_id']}"
    texto = chunk["text"]
    span = find_literal_span(quote, texto)
    if span:
        ini, fin, ratio, literal = *span, 1.0, True
    else:
        aln = fuzz.partial_ratio_alignment(quote, texto)
        ratio = (aln.score if aln else 0.0) / 100.0
        if ratio < min_ratio:
            return None, f"quote no encontrada en {ev['chunk_id']} (ratio {ratio:.2f})"
        ini, fin = _a_palabras(texto, aln.dest_start, aln.dest_end)
        distinto = mismo_sentido(quote, texto[ini:fin])
        if distinto:
            return None, f"paráfrasis que cambia el sentido en {ev['chunk_id']} (ratio {ratio:.2f}): {distinto}"
        literal = False
    out = {
        "chunk_id": chunk["chunk_id"],
        "doc": chunk["doc"],
        "section": chunk.get("section", ""),
        "page": page_of(chunk, ini),
        "quote": _como_se_lee(texto[ini:fin]),          # el texto del documento, no el del modelo
        "match_ratio": round(ratio, 3),
        "literal": literal,
    }
    if not literal:
        out["quote_modelo"] = quote                      # lo que escribió el modelo, para auditar la diferencia
    return out, None


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
            if not ok["literal"]:
                flags.append(f"cita_aproximada:{ok['chunk_id']} ({ok['match_ratio']:.2f}): se muestra el texto del documento")
        else:
            flags.append(f"quote_failed:{why}")
    if status != open_value and not verified:
        flags.append(f"demoted:{status}->{open_value}")
        status = open_value
    elif status != open_value and not any(v["literal"] for v in verified):
        flags.append("solo_citas_aproximadas: revisar antes de firmar")
    return status, verified, flags
