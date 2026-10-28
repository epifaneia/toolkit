"""Pruebas del montaje y del esqueleto. Sin red: el paso 4 es un stub.

    python tests/test_montaje.py

Se prueba la cadena (actor obligatorio, checkpoints que se reutilizan solo si
la entrada y la versión no cambiaron, artefactos JSON) y el esqueleto entero de
punta a punta, incluido el paso 5 degradando y marcando lo que no cuadra.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from esqueleto import run  # noqa: E402
from kit.custodia import cli, identity, ledger  # noqa: E402
from kit.montaje.cadena import Cadena, Paso  # noqa: E402
from kit.proceso.stub import Stub  # noqa: E402

fallos = 0


def check(cond: bool, msg: str) -> None:
    global fallos
    print(("  ok  " if cond else "  FAIL") + " " + msg)
    if not cond:
        fallos += 1


def cadena(tmp: Path) -> None:
    llamadas = []

    def doble(x):
        llamadas.append(x)
        return {"n": x["n"] * 2}

    pasos = [Paso("doble", doble), Paso("mas_uno", lambda x: {"n": x["n"] + 1})]
    os.environ.pop(identity.ENV_VAR, None)
    try:
        Cadena(pasos).correr({"n": 1})
        check(False, "sin actor debe fallar")
    except identity.MissingActor:
        check(True, "sin actor la cadena no corre")
    os.environ[identity.ENV_VAR] = "ana.garcia"

    c = Cadena(pasos, carpeta=tmp / "cp")
    check(c.correr({"n": 1}) == {"n": 3}, "encadena: la salida de un paso es la entrada del siguiente")
    guardado = json.loads((tmp / "cp" / "01_doble.json").read_text(encoding="utf-8"))
    check(guardado["salida"] == {"n": 2} and guardado["actor"] == "ana.garcia", "checkpoint con salida y actor")
    check(c.correr({"n": 1}) == {"n": 3} and len(llamadas) == 1, "misma entrada: se lee del checkpoint")
    c.correr({"n": 5})
    check(len(llamadas) == 2, "entrada distinta: se recalcula")
    Cadena([Paso("doble", doble, version="v2"), pasos[1]], carpeta=tmp / "cp").correr({"n": 5})
    check(len(llamadas) == 3, "versión distinta: se recalcula")
    c.correr({"n": 5}, reanudar=False)
    check(len(llamadas) == 4, "reanudar=False: siempre recalcula")
    try:
        Cadena([Paso("ruta", lambda x: Path("a"))], carpeta=tmp / "cp2").correr({})
        check(False, "un artefacto que no es JSON debe fallar")
    except TypeError as e:
        check("ruta" in str(e), "artefacto no JSON → TypeError con el nombre del paso")


def esqueleto(tmp: Path) -> None:
    ledger._default = ledger.Ledger(tmp / "custody.jsonl")
    entrada = {"documento": str(run.MANUAL), "pregunta": "¿Qué significa E3?"}

    salida = run.montar(Stub(), carpeta=tmp / "e1").correr(entrada)
    check(salida["estado"] == "respondida" and salida["marcas"] == [], "esqueleto con stub: corre de punta a punta")
    check(len(list((tmp / "e1").glob("0*_s*.json"))) == 5, "esqueleto: un checkpoint por paso")
    s3 = json.loads((tmp / "e1" / "03_s3_guardarrail_in.json").read_text(encoding="utf-8"))["salida"]
    check(any("E3" in u["texto"] for u in s3["unidades"]), "s2+s3: el trozo de los códigos de error llega al modelo")

    def responde(citas, estado):
        return Stub(responder=lambda p: {"citas": citas, "respuesta": "x", "estado": estado})

    e3 = next(u["id"] for u in s3["unidades"] if u["texto"].startswith("E3"))
    salida = run.montar(responde([e3], "respondida"), carpeta=tmp / "e2").correr(entrada)
    check(salida["citas"][0]["texto"].startswith("E3: fallo de temperatura"), "s5: la cita sale del documento")
    salida = run.montar(responde(["999"], "respondida"), carpeta=tmp / "e3").correr(entrada)
    check(salida["estado"] == "sin_evidencia" and salida["marcas"] == ["cita_inexistente:999",
          "degradada:respondida_sin_citas"], "s5: cita inexistente → se marca y se degrada")
    salida = run.montar(responde([e3], "sin_evidencia"), carpeta=tmp / "e4").correr(entrada)
    check(salida["marcas"] == ["incoherente:sin_evidencia_con_citas"] and salida["estado"] == "sin_evidencia",
          "s5: incoherencia → se marca, no se corrige")
    evento = json.loads((tmp / "custody.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    check(evento["step"] == "s4_proceso" and evento["actor"] == "ana.garcia", "esqueleto: s4 queda en el ledger")


def firma(tmp: Path) -> None:
    salida = tmp / "salida.json"
    salida.write_text("{}", encoding="utf-8")
    os.environ["CUSTODIA_SIGNING_KEY"] = "clave-local-de-prueba"
    check(cli.main(["sign", str(salida)]) == 0, "cli: firma la salida")
    check(cli.main(["verify", str(salida)]) == 0, "cli: la firma verifica")


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    for nombre, prueba in [("cadena", cadena), ("esqueleto", esqueleto), ("firma", firma)]:
        print(f"\n{nombre}")
        prueba(tmp)
    print(f"\n{'TODO OK' if fallos == 0 else f'{fallos} fallos'}")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
