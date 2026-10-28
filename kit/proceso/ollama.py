"""ollama — modelo local. Nada sale de la máquina.

Habla con un servidor Ollama (por defecto http://127.0.0.1:11434) y fuerza la
salida con JSON Schema: el decodificador solo puede emitir lo que el schema
permite, así que un enum cerrado está garantizado, no prometido en el prompt.

Dos cosas que aquí importan:

  · Dialecto del schema. Gemini usa el dialecto OpenAPI ("type": "OBJECT");
    Ollama espera JSON Schema puro ("type": "object"). `to_json_schema()`
    acepta los dos. Sin esa traducción el enum no se aplica.

  · Ventana de contexto. Ollama recorta el prompt a `num_ctx` EN SILENCIO (por
    defecto 4096 tokens). El modelo respondería sobre un documento que no ha
    visto entero, sin un solo aviso. Por eso `num_ctx` es explícito,
    `assert_fits()` se niega a enviar lo que no cabe, y si aun así el contador
    de Ollama toca el límite, la respuesta se descarta.

Configuración por entorno: OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_NUM_CTX.
Sin SDK: solo urllib de la stdlib.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from .contrato import NoDisponible, Peticion, Rechazada, Respuesta, RespuestaInvalida

_TYPES = {"OBJECT": "object", "STRING": "string", "ARRAY": "array",
          "INTEGER": "integer", "NUMBER": "number", "BOOLEAN": "boolean"}

# Estimador de tokens a la baja en caracteres por token: cuenta de más a
# propósito, para que ante la duda se niegue a enviar.
_CHARS_PER_TOKEN = 3.2


def _env(nombre: str, defecto: str) -> str:
    return os.environ.get(nombre, "").strip() or defecto


@dataclass
class Ollama:
    modelo: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "qwen2.5:7b"))
    base_url: str = field(default_factory=lambda: _env("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    num_ctx: int = field(default_factory=lambda: int(_env("OLLAMA_NUM_CTX", "16384")))
    temperatura: float = 0.1
    timeout_s: float = 1200.0
    motor: str = "ollama"
    sale_de_la_maquina: bool = False

    @property
    def endpoint(self) -> str:
        return self.base_url.split("//")[-1].rstrip("/")

    def generar(self, peticion: Peticion) -> Respuesta:
        texto, raw = chat(
            base_url=self.base_url, model=self.modelo, user_text=peticion.entrada,
            system_instruction=peticion.sistema or None, response_schema=peticion.schema,
            temperature=self.temperatura, num_ctx=self.num_ctx, timeout_s=self.timeout_s,
            **peticion.opciones,
        )
        salida = _json(texto) if peticion.schema else texto
        meta = {"input_tokens": raw.get("prompt_eval_count"), "output_tokens": raw.get("eval_count")}
        return Respuesta(salida=salida, motor=self.motor, modelo=self.modelo, meta=meta)


def chat(*, base_url: str, model: str, user_text: str, response_schema: dict | None = None,
         system_instruction: str | None = None, temperature: float = 0.1,
         num_ctx: int = 16384, num_gpu: int | None = None, num_thread: int | None = None,
         timeout_s: float = 1200.0) -> tuple[str, dict]:
    """Una llamada a /api/chat. → (texto de la respuesta, respuesta cruda)."""
    assert_fits(system=system_instruction or "", user=user_text, num_ctx=num_ctx)

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": user_text})

    body: dict[str, Any] = {
        "model": model, "messages": messages, "stream": False,
        "options": {"temperature": temperature, "num_ctx": num_ctx},
    }
    if response_schema:
        body["format"] = to_json_schema(response_schema)
    # num_gpu: capas en VRAM (el ajuste automático deja VRAM libre y cada capa
    # en CPU cuesta velocidad). num_thread: por defecto usa la mitad de núcleos.
    if num_gpu is not None:
        body["options"]["num_gpu"] = num_gpu
    if num_thread is not None:
        body["options"]["num_thread"] = num_thread
    raw = _post(f"{base_url.rstrip('/')}/api/chat", body, timeout_s=timeout_s)

    ev = raw.get("prompt_eval_count")
    if isinstance(ev, int) and ev >= num_ctx - 8:
        raise RespuestaInvalida(
            f"prompt_eval_count={ev} tocó num_ctx={num_ctx}: Ollama recortó el prompt. "
            "Respuesta descartada.")

    texto = ((raw.get("message") or {}).get("content") or "").strip()
    if not texto:
        raise RespuestaInvalida(f"Ollama sin contenido: {str(raw)[:300]}")
    return texto, raw


def generate_json_schema(*, response_schema: dict, **kw) -> Any:
    """Atajo sin contrato: salida forzada por schema → objeto Python."""
    texto, _ = chat(response_schema=response_schema, **kw)
    return _json(texto)


def to_json_schema(schema: Any) -> Any:
    """Dialecto OpenAPI (tipos en MAYÚSCULAS) → JSON Schema puro, recursivo."""
    if isinstance(schema, list):
        return [to_json_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for k, v in schema.items():
        if k == "type" and isinstance(v, str):
            out[k] = _TYPES.get(v.upper(), v.lower())
        elif k in ("properties", "$defs") and isinstance(v, dict):
            # mapa nombre → schema: se recorre por los valores, no el mapa
            out[k] = {name: to_json_schema(sub) for name, sub in v.items()}
        elif k == "items":
            out[k] = to_json_schema(v)
        else:
            out[k] = v
    if out.get("type") == "object" and "properties" in out:
        out.setdefault("additionalProperties", False)
    return out


def estimate_tokens(text: str) -> int:
    return int(len(text) / _CHARS_PER_TOKEN) + 1


def assert_fits(*, system: str, user: str, num_ctx: int, reserve: int = 1024) -> None:
    """Rechazada si el prompt no cabe en num_ctx (Ollama lo recortaría en silencio)."""
    need = estimate_tokens(system) + estimate_tokens(user) + reserve
    if need > num_ctx:
        raise Rechazada(
            f"prompt ~{need} tokens > num_ctx {num_ctx}: Ollama lo recortaría en silencio. "
            "Sube OLLAMA_NUM_CTX o manda menos contexto.")


def _json(texto: str) -> Any:
    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        raise RespuestaInvalida(f"Ollama devolvió algo que no es JSON: {texto[:200]}") from e


def _post(url: str, body: dict, *, timeout_s: float) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:300]
        if e.code == 404:   # el modelo no está descargado
            raise NoDisponible(f"Ollama 404: {detalle}. Prueba 'ollama pull <modelo>'.") from e
        raise RespuestaInvalida(f"Ollama {e.code}: {detalle}") from e
    except urllib.error.URLError as e:
        raise NoDisponible(f"Ollama no responde en {url} ({e.reason}). ¿Está 'ollama serve' en marcha?") from e
