"""gemini — modelo en la nube. El dato sale de la máquina y el ledger lo dice.

Llama a generateContent con salida estructurada: `responseSchema` la impone
la API, así que la respuesta ES el schema (enums cerrados garantizados). El
schema llega en JSON Schema, como al resto de adaptadores, y aquí se traduce
al dialecto OpenAPI que espera Gemini (`to_openapi_schema`).

La clave va en la cabecera `x-goog-api-key`, nunca en la URL: una URL acaba en
logs y trazas de error.

Configuración por entorno: GEMINI_API_KEY, GEMINI_MODEL.
Sin SDK: solo urllib de la stdlib.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contrato import NoDisponible, Peticion, Respuesta, RespuestaInvalida
from .json_helpers import extract_json_from_llm

HOST = "generativelanguage.googleapis.com"
_URL = f"https://{HOST}/v1beta/models/{{model}}:generateContent"


@dataclass
class Gemini:
    modelo: str = field(default_factory=lambda: os.environ.get("GEMINI_MODEL", "").strip() or "gemini-2.5-flash")
    api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", "").strip(), repr=False)
    temperatura: float = 0.2
    timeout_s: float = 300.0
    motor: str = "gemini"
    endpoint: str = HOST
    sale_de_la_maquina: bool = True

    def generar(self, peticion: Peticion) -> Respuesta:
        if not self.api_key:
            raise NoDisponible("Falta GEMINI_API_KEY en el entorno (.env).")
        texto, raw = generate(
            api_key=self.api_key, model=self.modelo, user_text=peticion.entrada,
            system_instruction=peticion.sistema or None, response_schema=peticion.schema,
            temperature=self.temperatura, timeout_s=self.timeout_s, **peticion.opciones,
        )
        salida = _json(texto) if peticion.schema else texto
        uso = raw.get("usageMetadata") or {}
        meta = {"input_tokens": uso.get("promptTokenCount"), "output_tokens": uso.get("candidatesTokenCount")}
        return Respuesta(salida=salida, motor=self.motor, modelo=self.modelo, meta=meta)


def generate(*, api_key: str, model: str, user_text: str, response_schema: dict | None = None,
             system_instruction: str | None = None, pdf_path: str | Path | None = None,
             temperature: float = 0.2, timeout_s: float = 300.0) -> tuple[str, dict]:
    """Una llamada a generateContent. → (texto de la respuesta, respuesta cruda).

    `pdf_path` adjunta un PDF inline (hasta ~20 MB; por encima hace falta la
    File API, que no está aquí).
    """
    parts: list[dict] = []
    if pdf_path:
        p = Path(pdf_path)
        if not p.is_file():
            raise FileNotFoundError(f"PDF no encontrado: {p}")
        parts.append({"inline_data": {"mime_type": "application/pdf",
                                      "data": base64.b64encode(p.read_bytes()).decode("ascii")}})
    parts.append({"text": user_text})

    config: dict[str, Any] = {"temperature": temperature}
    if response_schema:
        config["responseMimeType"] = "application/json"
        config["responseSchema"] = to_openapi_schema(response_schema)
    body: dict[str, Any] = {"contents": [{"role": "user", "parts": parts}], "generationConfig": config}
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    raw = _post(_URL.format(model=model), body, api_key=api_key, timeout_s=timeout_s)
    return _texto(raw), raw


def generate_json_schema(*, response_schema: dict, **kw) -> Any:
    """Atajo sin contrato: salida forzada por schema → objeto Python."""
    texto, _ = generate(response_schema=response_schema, **kw)
    return _json(texto)


def generate_json(**kw) -> Any:
    """Atajo sin schema: el primer JSON válido de la respuesta (el prompt lo pide)."""
    texto, _ = generate(**kw)
    return extract_json_from_llm(texto)


def to_openapi_schema(schema: Any) -> Any:
    """JSON Schema → dialecto OpenAPI de Gemini: tipos en MAYÚSCULAS y sin
    `additionalProperties` ni `$schema`, que responseSchema no admite."""
    if isinstance(schema, list):
        return [to_openapi_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for k, v in schema.items():
        if k in ("additionalProperties", "$schema"):
            continue
        if k == "type" and isinstance(v, str):
            out[k] = v.upper()
        elif k == "properties" and isinstance(v, dict):
            out[k] = {name: to_openapi_schema(sub) for name, sub in v.items()}
        elif k == "items":
            out[k] = to_openapi_schema(v)
        else:
            out[k] = v
    return out


def _json(texto: str) -> Any:
    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        raise RespuestaInvalida(f"Gemini devolvió algo que no es JSON: {texto[:200]}") from e


def _texto(raw: dict) -> str:
    candidatos = raw.get("candidates") or []
    if not candidatos:
        raise RespuestaInvalida(f"Gemini sin candidates: {str(raw)[:300]}")
    parts = (candidatos[0].get("content") or {}).get("parts") or []
    texto = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    if not texto:
        motivo = candidatos[0].get("finishReason", "?")
        raise RespuestaInvalida(f"Gemini sin texto (finishReason={motivo})")
    return texto


def _post(url: str, body: dict, *, api_key: str, timeout_s: float) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json", "x-goog-api-key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 403):
            raise NoDisponible(f"Gemini {e.code}: la clave no vale para este modelo. {detalle}") from e
        raise RespuestaInvalida(f"Gemini {e.code}: {detalle}") from e
    except urllib.error.URLError as e:
        raise NoDisponible(f"Sin conexión con {HOST} ({e.reason}).") from e
