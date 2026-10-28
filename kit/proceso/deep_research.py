"""deep_research — un agente de investigación en la nube que tarda minutos.

Usa la Interactions API de Gemini (SDK google-genai): la petición se lanza en
segundo plano, se consulta su estado cada `intervalo_s` y, al completarse, se
devuelve el informe en texto. Es la llamada del validador de ideas de empresa
(repositorio feasibility-study).

Dos detalles que costaron un informe cortado:
  · El informe llega repartido en VARIOS pasos de salida del modelo; hay que
    concatenarlos todos. `output_text` solo trae el último bloque.
  · Hay un tope de espera (`timeout_s`). Pasado, se abandona con el ID en el
    mensaje para poder recuperarlo después.

No admite schema: devuelve texto. Si hace falta estructura, la saca un segundo
paso con salida forzada (Gemini u Ollama) sobre ese texto.

Configuración por entorno: GEMINI_API_KEY, DEEP_RESEARCH_AGENT, RESEARCH_TIMEOUT_S.
Necesita `pip install google-genai`.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .contrato import NoDisponible, Peticion, Respuesta, RespuestaInvalida

_FALLOS = {"failed", "cancelled", "incomplete", "budget_exceeded"}


@dataclass
class DeepResearch:
    modelo: str = field(default_factory=lambda: os.environ.get("DEEP_RESEARCH_AGENT", "").strip()
                        or "deep-research-preview-04-2026")
    timeout_s: float = field(default_factory=lambda: float(os.environ.get("RESEARCH_TIMEOUT_S", 45 * 60)))
    intervalo_s: float = 30.0
    cliente: Any = None                               # genai.Client; los tests pasan uno falso
    esperar: Callable[[float], None] = time.sleep
    motor: str = "gemini-deep-research"
    endpoint: str = "generativelanguage.googleapis.com"
    sale_de_la_maquina: bool = True

    def generar(self, peticion: Peticion) -> Respuesta:
        cliente = self.cliente or _cliente()
        interaccion = cliente.interactions.create(
            input=peticion.entrada, agent=self.modelo, background=True, store=True)
        inicio = time.monotonic()
        while True:
            interaccion = cliente.interactions.get(interaccion.id)
            estado = str(interaccion.status)
            if estado == "completed":
                texto = informe(interaccion)
                return Respuesta(salida=texto, motor=self.motor, modelo=self.modelo,
                                 meta={"interaction_id": interaccion.id})
            if estado in _FALLOS:
                raise RespuestaInvalida(f"El research {interaccion.id} terminó en estado '{estado}'.")
            if time.monotonic() - inicio > self.timeout_s:
                raise RespuestaInvalida(f"El research {interaccion.id} pasó de {self.timeout_s:.0f} s; "
                                        "abandonado (se puede consultar por su ID).")
            self.esperar(self.intervalo_s)


def informe(interaccion: Any) -> str:
    """Concatena TODOS los pasos de salida del modelo, no solo el último."""
    partes = []
    for paso in getattr(interaccion, "steps", None) or []:
        if getattr(paso, "type", None) != "model_output" and type(paso).__name__ != "ModelOutputStep":
            continue
        partes += [c.text for c in getattr(paso, "content", None) or [] if getattr(c, "text", None)]
    if partes:
        return "\n".join(partes)
    if getattr(interaccion, "output_text", None):
        return interaccion.output_text
    raise RespuestaInvalida("El research se completó sin devolver texto.")


def _cliente() -> Any:
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        raise NoDisponible("Falta GEMINI_API_KEY en el entorno (.env).")
    try:
        from google import genai
    except ImportError as e:
        raise NoDisponible("Falta el SDK: pip install google-genai") from e
    return genai.Client()
