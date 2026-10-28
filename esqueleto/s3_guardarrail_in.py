"""Paso 3 · Guardarraíl de entrada. Código: acota lo que el modelo puede responder.

El modelo no escribe citas: elige números de una lista cerrada (el enum del
schema). El texto de la cita lo pondrá el paso 5, copiado del documento.
"""
from __future__ import annotations

from kit.guardarrail_in.citables import trocear

SISTEMA = ("Respondes solo con lo que dicen las frases numeradas. Cita los números de las "
           "frases que lo dicen y el estado es respondida. Si ninguna lo dice, no citas nada, "
           "la respuesta queda vacía y el estado es sin_evidencia.")


def acotar(art: dict) -> dict:
    """→ {"pregunta", "unidades", "sistema", "prompt", "schema"}"""
    unidades = []
    for chunk in art["chunks"]:
        for u in trocear(chunk["text"]):
            unidades.append({"id": str(len(unidades)), "chunk_id": chunk["chunk_id"], "texto": u["texto"]})

    lista = "\n".join(f"[{u['id']}] {u['texto']}" for u in unidades)
    schema = {
        "type": "object",
        "properties": {     # en este orden: primero la evidencia, después el veredicto
            "citas": {"type": "array", "items": {"type": "string", "enum": [u["id"] for u in unidades]}},
            "respuesta": {"type": "string"},
            "estado": {"type": "string", "enum": ["respondida", "sin_evidencia"]},
        },
        "required": ["citas", "respuesta", "estado"],
    }
    return {"pregunta": art["pregunta"], "unidades": unidades, "sistema": SISTEMA,
            "prompt": f"Frases:\n{lista}\n\nPregunta: {art['pregunta']}", "schema": schema}
