"""Paso 5 · Guardarraíl de salida. Código: verifica, marca y degrada. Nunca corrige.

  · Las citas salen del documento, no del modelo: cada número se cambia por
    la frase que tiene ese número.
  · Un número que no existe se marca y no cuenta como evidencia.
  · "respondida" sin ninguna cita válida se degrada a "sin_evidencia".
  · "sin_evidencia" con citas es incoherente: se marca y se deja como está.
  · La respuesta del modelo pasa tal cual: este paso no la reescribe.
"""
from __future__ import annotations


def verificar(art: dict) -> dict:
    """→ {"pregunta", "estado", "respuesta", "citas", "marcas", "motor"}"""
    por_id = {u["id"]: u for u in art["unidades"]}
    propuesta = art["propuesta"]
    marcas = []

    citas = []
    for i in propuesta.get("citas", []):
        if i in por_id:
            citas.append({"chunk_id": por_id[i]["chunk_id"], "texto": por_id[i]["texto"]})
        else:
            marcas.append(f"cita_inexistente:{i}")

    estado = propuesta.get("estado")
    if estado == "respondida" and not citas:
        estado = "sin_evidencia"
        marcas.append("degradada:respondida_sin_citas")
    elif estado == "sin_evidencia" and citas:
        marcas.append("incoherente:sin_evidencia_con_citas")

    return {"pregunta": art["pregunta"], "estado": estado, "respuesta": propuesta.get("respuesta", ""),
            "citas": citas, "marcas": marcas, "motor": art["motor"]}
