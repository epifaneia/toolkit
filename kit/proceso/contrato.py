"""contrato — lo que comparten todos los adaptadores del paso 4.

Un adaptador por motor (Ollama, Gemini, deep research, Jev, Whisper, Kokoro),
todos con la misma forma:

    Peticion  → entrada (prompt, ruta de audio o texto a leer), sistema,
                schema (el contrato de la salida) y opciones del motor.
    Respuesta → salida (dict si hubo schema; str o Path si no), motor, modelo
                y meta (tokens, coste...: lo que el motor devuelva).
    Errores   → tres, y el pipeline decide qué hacer con cada uno:
                NoDisponible      el motor no se puede usar aquí (sin clave,
                                  sin paquete, servicio parado). Nada se envió.
                Rechazada         el adaptador se niega a enviar (no cabe,
                                  supera el tope de gasto). Nada se envió.
                RespuestaInvalida se envió y lo que volvió no sirve.

Cambiar de motor es cambiar el objeto, no el paso: `s4` no sabe si habla con
un modelo local, con la nube o con un stub.

Toda llamada pasa por `llamar()`, que la deja en el libro de custodia
(kit.custodia.ledger): actor, paso, motor, si el dato sale de la máquina y un
hash de la entrada. Nunca el texto.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from kit.custodia.ledger import record_call


class ErrorModelo(RuntimeError):
    """Base de los errores del paso 4."""


class NoDisponible(ErrorModelo):
    """El motor no se puede usar aquí: falta clave, paquete o servicio."""


class Rechazada(ErrorModelo):
    """El adaptador no envía la petición: no cabe o supera un tope."""


class RespuestaInvalida(ErrorModelo):
    """La llamada se hizo y lo que volvió no cumple el contrato."""


@dataclass(frozen=True)
class Peticion:
    entrada: str                    # prompt, ruta de audio (stt) o texto a leer (tts)
    sistema: str = ""               # instrucción de sistema, si el motor la admite
    schema: dict | None = None      # JSON Schema de la salida; None = texto libre
    opciones: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Respuesta:
    salida: Any                     # dict (con schema), str (texto) o Path (audio)
    motor: str
    modelo: str
    meta: dict = field(default_factory=dict)


class Modelo(Protocol):
    motor: str                      # "ollama", "gemini", "stub"...
    modelo: str                     # versión fijada del modelo
    endpoint: str                   # host al que va el dato, o "local"
    sale_de_la_maquina: bool

    def generar(self, peticion: Peticion) -> Respuesta: ...


def llamar(modelo: Modelo, peticion: Peticion, *, paso: str) -> Respuesta:
    """La única puerta al modelo: llama y deja el evento en el ledger."""
    huella = peticion.sistema + peticion.entrada + json.dumps(peticion.schema or {}, sort_keys=True)
    with record_call(step=paso, engine=modelo.motor, endpoint=modelo.endpoint,
                     leaves_machine=modelo.sale_de_la_maquina, payload=huella,
                     model=modelo.modelo) as rec:
        respuesta = modelo.generar(peticion)
        rec["output_chars"] = len(str(respuesta.salida))
        rec.update(respuesta.meta)
        return respuesta
