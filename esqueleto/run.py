"""Esqueleto de un pipeline de cinco pasos. Solo los pilares.

    python -m esqueleto.run                          # MOTOR=stub: sin red, sin claves
    python -m esqueleto.run "¿Qué significa E3?"     # otra pregunta
    MOTOR=ollama python -m esqueleto.run             # mismo código, modelo local
    MOTOR=gemini python -m esqueleto.run             # mismo código, nube

Cada paso es un módulo corto con una función. La cadena los encadena, guarda un
checkpoint por paso en data/esqueleto/ y no corre sin actor (CUSTODIA_ACTOR).
"""
from __future__ import annotations

import json
import os
import sys
from functools import partial
from pathlib import Path

from esqueleto import s1_limpieza, s2_contexto, s3_guardarrail_in, s4_proceso, s5_guardarrail_out
from kit.custodia.identity import MissingActor
from kit.montaje.cadena import Cadena, Paso
from kit.proceso import motores
from kit.proceso.contrato import ErrorModelo

MANUAL = Path(__file__).parent / "muestra" / "manual.txt"
CARPETA = Path("data") / "esqueleto"


def montar(modelo, carpeta: Path = CARPETA) -> Cadena:
    return Cadena([
        Paso("s1_limpieza", s1_limpieza.limpiar),
        Paso("s2_contexto", s2_contexto.recuperar),
        Paso("s3_guardarrail_in", s3_guardarrail_in.acotar),
        Paso("s4_proceso", partial(s4_proceso.decidir, modelo=modelo), version=f"{modelo.motor}:{modelo.modelo}"),
        Paso("s5_guardarrail_out", s5_guardarrail_out.verificar),
    ], carpeta=carpeta)


def main(argv: list[str]) -> int:
    _cargar_env(Path(".env"))
    pregunta = argv[0] if argv else "¿Cada cuánto hay que cambiar el filtro de agua?"
    modelo = motores.crear()
    print(f"motor: {modelo.motor}:{modelo.modelo}  (sale de la máquina: {modelo.sale_de_la_maquina})")
    try:
        salida = montar(modelo).correr({"documento": str(MANUAL), "pregunta": pregunta})
    except MissingActor as e:
        print(e)
        return 2
    except ErrorModelo as e:
        print(f"paso 4: {type(e).__name__}: {e}")
        return 3

    fichero = CARPETA / "salida.json"
    fichero.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(salida, ensure_ascii=False, indent=2))
    print(f"\nPropuesta en {fichero}. Hasta que alguien la firme no sale de aquí:\n"
          f"  python -m kit.custodia.cli sign {fichero}")
    return 0


def _cargar_env(ruta: Path) -> None:
    """Lee KEY=valor de .env sin pisar lo que ya esté en el entorno."""
    if ruta.is_file():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            clave, igual, valor = linea.partition("=")
            if igual and not clave.lstrip().startswith("#"):
                os.environ.setdefault(clave.strip(), valor.split(" #")[0].strip())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
