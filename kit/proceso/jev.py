"""jev — un modelo que no escribe: decide entre opciones cerradas.

Jev (TypeSafe, vía OpenRouter, POST /api/alpha/decisions) recibe un `state`
(lo que tiene que leer) y un mapa de preguntas cerradas, y devuelve por cada
una probabilidades sobre las opciones dadas. Aquí encaja en el contrato así:

    Peticion.entrada → el state
    Peticion.schema  → las preguntas: {id: {"type": "choice", "criteria": {...}}, ...}
                       choice (elige una opción), score (nivel en una escala)
                       o noul (probabilidad de "sí")
    Respuesta.salida → {id: respuesta}, con los campos opcionales explícitos

Gastar dinero es una decisión, no un efecto de tener la clave: antes de cada
llamada se suma el coste real ya registrado en el ledger (campo `cost`) más la
estimación de esta petición, y si pasa del tope (JEV_TOPE_USD), no se envía.
El coste lo apunta `contrato.llamar()`: llamar a `generar()` a pelo deja el
tope sin datos.
Tampoco se envía una petición de más de ~30.000 bytes: por encima de ~32.000
TypeSafe pasa a contexto largo, más lento y menos preciso.

Configuración por entorno: OPENROUTER_API_KEY, JEV_MODEL, JEV_TOPE_USD.
Sin SDK: solo urllib de la stdlib.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from kit.custodia import ledger

from .contrato import NoDisponible, Peticion, Rechazada, Respuesta, RespuestaInvalida

URL = "https://openrouter.ai/api/alpha/decisions"
PRECIO_ENTRADA = 0.042 / 1_000_000   # $ por token de entrada, la salida no se cobra (OpenRouter, 2026-10-28)
BYTES_POR_TOKEN = 3.0                # a la baja: sobreestima el coste
LIMITE_BYTES = 30_000


@dataclass
class Jev:
    modelo: str = field(default_factory=lambda: os.environ.get("JEV_MODEL", "").strip() or "typesafe/jev-1.14")
    tope_usd: float = field(default_factory=lambda: float(os.environ.get("JEV_TOPE_USD", "0.25")))
    api_key: str = field(default_factory=lambda: os.environ.get("OPENROUTER_API_KEY", "").strip(), repr=False)
    timeout_s: float = 60.0
    motor: str = "jev"
    endpoint: str = "openrouter.ai"
    sale_de_la_maquina: bool = True

    def generar(self, peticion: Peticion) -> Respuesta:
        if not self.api_key:
            raise NoDisponible("Falta OPENROUTER_API_KEY en el entorno (.env).")
        preguntas = peticion.schema or {}
        cuerpo = json.dumps({"model": self.modelo, "state": peticion.entrada, "questions": preguntas},
                            ensure_ascii=False)
        self._comprobar(cuerpo)
        raw = _post(cuerpo, self.api_key, self.timeout_s)
        respuestas = raw.get("answers") or {}
        faltan = set(preguntas) - set(respuestas)
        if faltan:
            raise RespuestaInvalida(f"Jev no contestó a {sorted(faltan)}")
        uso = raw.get("usage") or {}
        return Respuesta(salida={q: normalizar(a) for q, a in respuestas.items()},
                         motor=self.motor, modelo=raw.get("model", self.modelo),
                         meta={"cost": uso.get("cost"), "input_tokens": uso.get("input_tokens")})

    def _comprobar(self, cuerpo: str) -> None:
        tamano = len(cuerpo.encode("utf-8"))
        if tamano > LIMITE_BYTES:
            raise Rechazada(f"Petición de {tamano} bytes > {LIMITE_BYTES}: Jev pasaría a contexto largo.")
        gastado, estimado = gasto_acumulado(), tamano / BYTES_POR_TOKEN * PRECIO_ENTRADA
        if gastado + estimado > self.tope_usd:
            raise Rechazada(f"Gastado {gastado:.6f} $ + estimado {estimado:.6f} $ > tope "
                            f"{self.tope_usd} $ (JEV_TOPE_USD). No se envía.")


def gasto_acumulado() -> float:
    """Suma del coste real que OpenRouter devolvió, según el ledger."""
    path = ledger.default().path
    if not path or not path.is_file():
        return 0.0
    filas = (json.loads(linea) for linea in path.read_text(encoding="utf-8").splitlines())
    return sum(r.get("cost") or 0.0 for r in filas if r.get("engine") == "jev")


def normalizar(a: dict) -> dict:
    """Sin confianza es confianza 0 (el paso 5 lo marca como dudoso); sin
    probabilidades, la opción elegida se queda con su confianza."""
    a = dict(a)
    if a.get("type") in ("choice", "score"):
        a.setdefault("confidence", 0.0)
    if a.get("type") == "choice":
        a.setdefault("probabilities", {a["choice"]: a["confidence"]})
    return a


def _post(cuerpo: str, key: str, timeout_s: float) -> dict:
    req = urllib.request.Request(URL, data=cuerpo.encode("utf-8"), method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 402, 403):
            raise NoDisponible(f"OpenRouter {e.code}: {detalle}") from e
        raise RespuestaInvalida(f"OpenRouter {e.code}: {detalle}") from e
    except urllib.error.URLError as e:
        raise NoDisponible(f"Sin conexión con openrouter.ai ({e.reason}).") from e
