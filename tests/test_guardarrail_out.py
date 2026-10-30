"""Pruebas de quote_verify: la cita que sale es siempre texto del documento, y una
paráfrasis solo vale si conserva cifras y negaciones. Sin red, sin modelos.

    python tests/test_guardarrail_out.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kit.guardarrail_out.quote_verify import citation, seal, verify_evidence  # noqa: E402

TEXTO = ("4.2 Frenado\nEl sistema debe liberar el freno de estacionamiento en menos de 200 ms "
         "tras la orden del conductor.\nEl oscilador externo de 3 a 25 MHz da una fre-\ncuencia "
         "muy precisa al reloj principal.")
CHUNK = {"chunk_id": "SPEC-C001", "doc": "SPEC", "section": "§4.2 Frenado", "text": TEXTO,
         "page_start": 12, "page_map": [{"offset": 0, "page": 12}, {"offset": TEXTO.index("El oscilador"), "page": 13}]}
CHUNKS = {CHUNK["chunk_id"]: CHUNK}
fallos = 0


def check(cond: bool, msg: str, detalle=None) -> None:
    global fallos
    print(("  ok  " if cond else "  FAIL") + " " + msg + ("" if cond or detalle is None else f"  -> {detalle}"))
    if not cond:
        fallos += 1


def verificar(quote: str, chunk_id: str = "SPEC-C001"):
    return verify_evidence({"chunk_id": chunk_id, "quote": quote}, CHUNKS)


print("literal")
ok, _ = verificar("El oscilador externo de 3 a 25 MHz da una frecuencia muy precisa al reloj principal.")
check(ok and ok["literal"] and ok["match_ratio"] == 1.0, "literal pese a la palabra partida en dos líneas", ok)
check(ok and ok["page"] == 13 and "quote_modelo" not in ok, "la página sale del offset y no hay rastro de paráfrasis", ok)

print("paráfrasis")
ok, why = verificar("El sistema no debe liberar el freno de estacionamiento en menos de 200 ms tras la orden del conductor.")
check(ok is None and "negación" in why, "una negación añadida no pasa, aunque se parezca un 96 %", why)
ok, why = verificar("El sistema debe liberar freno de estacionamiento en menos de 500 ms tras la orden del conductor.")
check(ok is None and "cifras distintas" in why, "una cifra cambiada no pasa", why)
ok, why = verificar("El oscilador externo de 4 a 16 MHz da una frecuencia muy precisa al reloj principal.")
check(ok is None and "cifras distintas" in why, "el caso de los MHz: 4 a 16 frente a 3 a 25", why)
ok, why = verificar("El sistema debe liberar el freno de estacionamiento en menos de 200 ms tras la orden de conductor.")
check(ok is not None and not ok["literal"], "una paráfrasis que solo cambia una palabra menor pasa como aproximada", why)
check(ok and ok["quote"].startswith("El sistema debe liberar el freno") and "del conductor" in ok["quote"],
      "y lo que se devuelve es el texto del documento, no el del modelo", ok and ok["quote"])
check(ok and ok["quote_modelo"].endswith("orden de conductor."), "lo que escribió el modelo queda aparte")

print("descartes")
ok, why = verificar("La batería admite 100 000 ciclos de carga en todo el rango de temperatura.")
check(ok is None and "no encontrada" in why, "lo que no está en el documento se descarta", why)
ok, why = verificar("El sistema debe liberar el freno de estacionamiento.", "SPEC-C999")
check(ok is None and "inexistente" in why, "un chunk que no existe se descarta", why)
ok, why = verificar("freno")
check(ok is None and "corta" in why, "una cita demasiado corta se descarta", why)

print("cortes y cifras (casos de la revisión del 30 oct)")
T2 = ("5.1 Requisitos\nEl freno no debe liberarse mientras el motor esté apagado. Rango de -40 °C a 85 °C. "
      "Consumo máximo de 1200 mA. Alimentación entre 9-16 V. El par de apriete es de 25 Nm. "
      "Tiempo de arranque 3,6 s. No obstante, el sistema debe arrancar en frío.")
CHUNKS["SPEC-C002"] = {"chunk_id": "SPEC-C002", "doc": "SPEC", "section": "§5.1", "text": T2,
                       "page_start": 20, "page_map": [{"offset": 0, "page": 20}]}


def v2(quote: str):
    return verify_evidence({"chunk_id": "SPEC-C002", "quote": quote}, CHUNKS)


ok, why = v2("debe liberarse mientras el motor esté apagado")
check(ok is None and "deja fuera la negación" in why, "un trozo literal que deja fuera el «no» de delante no pasa", why)
ok, why = v2("40 °C a 85 °C")
check(ok is None and "cifras distintas" in why, "«40 °C» no está dentro de «-40 °C»: el signo es parte de la cifra", why)
ok, why = v2("Consumo máximo de 200 mA")
check(ok is None, "«200 mA» no está dentro de «1200 mA»", why)
ok, why = v2("Consumo mínimo de 1200 mA.")
check(ok is None and "máximo/mínimo" in why, "máximo cambiado por mínimo no pasa como paráfrasis", why)
ok, why = v2("El par de apriete es de 25 Ncm.")
check(ok is None and "cifras distintas" in why, "Nm cambiado por Ncm no pasa", why)
ok, why = v2("Tiempo de arranque 6,3 s.")
check(ok is None and "cifras distintas" in why, "3,6 s cambiado por 6,3 s no pasa", why)
ok, why = v2("Alimentación entre 16-9 V.")
check(ok is None and "cifras distintas" in why, "el orden de las cifras cuenta: 9-16 no es 16-9", why)
ok, why = v2("Rango de 40 °C a 85 °C.")
check(ok is None and "cifras distintas" in why, "en paráfrasis, -40 y 40 tampoco son la misma cifra", why)
ok, why = v2("Alimentación entre 9-16 V.")
check(ok is not None and ok["literal"], "un rango con guion sigue siendo literal: «9-16» no tiene signo", why)
ok, why = v2("16 V. El par de apriete es de 25 Nm.")
check(ok is not None and ok["literal"], "y citar desde el segundo número del rango también vale", why)
ok, why = v2("el sistema debe arrancar en frío.")
check(ok is not None and ok["literal"], "«No obstante,» delante no es una negación de la frase citada", why)
ok, why = v2("Tiempo de arranque 3.6 s.")
check(ok is not None, "3,6 y 3.6 son la misma cifra", why)

print("seal")
literal = {"chunk_id": "SPEC-C001", "quote": "El sistema debe liberar el freno de estacionamiento en menos de 200 ms"}
negada = {"chunk_id": "SPEC-C001", "quote": "El sistema no debe liberar el freno de estacionamiento en menos de 200 ms"}
aprox = {"chunk_id": "SPEC-C001", "quote": "El sistema debe liberar el freno de estacionamiento en menos de 200 ms tras la orden de conductor"}
status, ev, flags = seal("cumple", [negada], CHUNKS, "abierto")
check(status == "abierto" and not ev and any(f.startswith("demoted:cumple->abierto") for f in flags),
      "con la única cita negada, el veredicto se degrada a abierto", (status, flags))
status, ev, flags = seal("cumple", [aprox], CHUNKS, "abierto")
check(status == "cumple" and any(f.startswith("solo_citas_aproximadas") for f in flags),
      "con solo citas aproximadas se mantiene, pero marcado para revisar antes de firmar", flags)
status, ev, flags = seal("cumple", [literal, aprox], CHUNKS, "abierto")
check(status == "cumple" and not any(f.startswith("solo_citas") for f in flags) and len(ev) == 2,
      "con una literal ya no hace falta esa marca", flags)
check(citation(ev[0]) == '[SPEC p.12 §4.2 Frenado] "El sistema debe liberar el freno de estacionamiento en menos de 200 ms"',
      "la cita la compone el código, con documento, página y sección", citation(ev[0]))

print("TODO OK" if not fallos else f"{fallos} FALLOS")
sys.exit(1 if fallos else 0)
