"""Paso 4 · Proceso. El único paso que llama a un modelo.

No sabe qué modelo es: recibe uno que cumple el contrato (stub, Ollama,
Gemini...) y llama a través de `llamar`, que lo deja en el ledger.
"""
from __future__ import annotations

from kit.proceso.contrato import Modelo, Peticion, llamar


def decidir(art: dict, *, modelo: Modelo) -> dict:
    """→ {"pregunta", "unidades", "propuesta", "motor"}"""
    peticion = Peticion(entrada=art["prompt"], sistema=art["sistema"], schema=art["schema"])
    r = llamar(modelo, peticion, paso="s4_proceso")
    return {"pregunta": art["pregunta"], "unidades": art["unidades"],
            "propuesta": r.salida, "motor": f"{r.motor}:{r.modelo}"}
