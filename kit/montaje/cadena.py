"""cadena — cómo se encadenan los cinco pasos.

Tres reglas, y el resto es código normal:

  1. Un paso es una función: artefacto de entrada → artefacto de salida.
     Nada de estado compartido; lo que un paso necesita, se lo pasa el anterior.
  2. Un artefacto es JSON plano (dict, list, str, números). Se puede abrir,
     comparar entre ejecuciones y guardar tal cual. Una ruta va como str.
  3. Cada paso deja un checkpoint: <carpeta>/NN_<paso>.json con la salida y el
     hash de lo que entró. Al repetir, un paso cuya entrada no cambió se lee
     del disco en vez de recalcularse. Lo que más se ahorra es el paso 4: no se
     vuelve a pagar una llamada al modelo para depurar el paso 5.
     Si cambia la configuración de un paso sin cambiar su entrada (otro motor,
     otro modelo), se declara en `version` y el checkpoint deja de valer.

La custodia va en la cadena, no en cada paso: sin actor con nombre no corre
(kit.custodia.identity), y cada checkpoint lleva quién lo produjo. Las
llamadas al modelo las registra `kit.proceso.contrato.llamar` en el ledger, y
la salida final es una propuesta hasta que alguien la firma (kit.custodia.cli).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from kit.custodia import identity


@dataclass(frozen=True)
class Paso:
    nombre: str                         # "s1_limpieza", "s4_proceso"...
    fn: Callable[[Any], Any]            # artefacto → artefacto
    version: str = ""                   # cambiarla invalida el checkpoint (p. ej. "ollama:qwen2.5:7b")


class Cadena:
    def __init__(self, pasos: list[Paso], carpeta: str | Path | None = None):
        self.pasos = pasos
        self.carpeta = Path(carpeta) if carpeta else None

    def correr(self, entrada: Any, *, reanudar: bool = True) -> Any:
        actor = identity.require_actor()
        artefacto = entrada
        for n, paso in enumerate(self.pasos, 1):
            artefacto = self._uno(n, paso, artefacto, actor, reanudar)
        return artefacto

    def _uno(self, n: int, paso: Paso, entrada: Any, actor: str, reanudar: bool) -> Any:
        huella = _sha(_json(entrada, paso.nombre) + paso.version)
        ruta = self.carpeta / f"{n:02d}_{paso.nombre}.json" if self.carpeta else None

        if reanudar and ruta and ruta.is_file():
            guardado = json.loads(ruta.read_text(encoding="utf-8"))
            if guardado.get("entrada_sha256") == huella:
                print(f"  {paso.nombre:<20} checkpoint")
                return guardado["salida"]

        t0 = time.perf_counter()
        salida = paso.fn(entrada)
        segundos = round(time.perf_counter() - t0, 3)
        print(f"  {paso.nombre:<20} {segundos:.2f} s")

        if ruta:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            registro = {"paso": paso.nombre, "version": paso.version, "actor": actor,
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "segundos": segundos,
                        "entrada_sha256": huella, "salida": salida}
            ruta.write_text(_json(registro, paso.nombre, indent=1), encoding="utf-8")
        return salida


def _json(dato: Any, paso: str, indent: int | None = None) -> str:
    try:
        return json.dumps(dato, ensure_ascii=False, sort_keys=True, indent=indent)
    except TypeError as e:
        raise TypeError(f"{paso}: el artefacto no es JSON plano ({e}). "
                        "Convierte rutas a str y objetos a dict.") from e


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
