"""stub — un modelo sin red y sin inteligencia, con el mismo contrato.

Sirve para correr el pipeline entero sin claves ni GPU: los pasos 1, 2, 3 y 5
se prueban de verdad y el 4 devuelve algo con la forma correcta.

Por defecto rellena el schema con lo mínimo válido (el primer valor de cada
enum, "(stub)" en cada texto, un elemento en cada lista). Si se le pasa
`responder`, devuelve lo que esa función diga: así un test fija la respuesta
que quiere poner a prueba.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .contrato import Peticion, Respuesta


@dataclass
class Stub:
    responder: Callable[[Peticion], Any] | None = None
    motor: str = "stub"
    modelo: str = "stub"
    endpoint: str = "local"
    sale_de_la_maquina: bool = False

    def generar(self, peticion: Peticion) -> Respuesta:
        if self.responder:
            salida = self.responder(peticion)
        elif peticion.schema:
            salida = minimo_valido(peticion.schema)
        else:
            salida = "(stub)"
        return Respuesta(salida=salida, motor=self.motor, modelo=self.modelo)


def minimo_valido(schema: dict) -> Any:
    """La instancia más pequeña que cumple un JSON Schema sencillo."""
    if "enum" in schema:
        return schema["enum"][0]
    tipo = str(schema.get("type", "string")).lower()
    if tipo == "object":
        return {k: minimo_valido(v) for k, v in schema.get("properties", {}).items()}
    if tipo == "array":
        return [minimo_valido(schema.get("items", {}))]
    return {"string": "(stub)", "integer": 0, "number": 0.0, "boolean": False}.get(tipo)
