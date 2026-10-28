"""Pruebas del paso 4: contrato y adaptadores. Sin red, sin claves, sin modelos.

    python tests/test_proceso.py

Cada adaptador se prueba con lo que hay alrededor de la llamada: cómo arma la
petición, qué hace con la respuesta y qué error lanza en cada fallo. La red se
sustituye por funciones falsas; los paquetes pesados (faster-whisper, kokoro,
google-genai) por módulos falsos. Lo que NO se prueba aquí es que el servicio
real responda: eso es `MOTOR=ollama python -m esqueleto.run`.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import types
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kit.custodia import ledger  # noqa: E402
from kit.proceso import deep_research, gemini, jev, kokoro, motores, ollama, whisper  # noqa: E402
from kit.proceso.contrato import (NoDisponible, Peticion, Rechazada,  # noqa: E402
                                  RespuestaInvalida, llamar)
from kit.proceso.stub import Stub, minimo_valido  # noqa: E402

fallos = 0
SCHEMA = {"type": "object", "properties": {
    "estado": {"type": "string", "enum": ["si", "no"]},
    "citas": {"type": "array", "items": {"type": "string", "enum": ["0", "1"]}}}}


def check(cond: bool, msg: str) -> None:
    global fallos
    print(("  ok  " if cond else "  FAIL") + " " + msg)
    if not cond:
        fallos += 1


def lanza(error: type, fn) -> bool:
    try:
        fn()
    except error:
        return True
    except Exception as e:  # otro error: también es fallo del test
        print(f"        (lanzó {type(e).__name__}: {e})")
    return False


def contrato_y_stub(tmp: Path) -> None:
    os.environ["CUSTODIA_ACTOR"] = "ana.garcia"
    ledger._default = ledger.Ledger(tmp / "custody.jsonl")
    check(minimo_valido(SCHEMA) == {"estado": "si", "citas": ["0"]}, "stub: mínimo válido de un schema")
    r = llamar(Stub(), Peticion(entrada="texto secreto", schema=SCHEMA), paso="s4")
    check(r.salida["estado"] == "si" and r.motor == "stub", "llamar devuelve la Respuesta del modelo")
    evento = json.loads((tmp / "custody.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    check(evento["step"] == "s4" and evento["engine"] == "stub" and evento["leaves_machine"] is False,
          "llamar deja el evento en el ledger")
    check("secreto" not in (tmp / "custody.jsonl").read_text(encoding="utf-8"), "el ledger no guarda el texto")
    r = llamar(Stub(responder=lambda p: {"eco": p.entrada}), Peticion(entrada="hola"), paso="s4")
    check(r.salida == {"eco": "hola"}, "stub con respuesta fijada por el test")
    check(Stub().generar(Peticion(entrada="x")).salida == "(stub)", "stub sin schema → texto")


def adaptador_ollama() -> None:
    enviado = {}

    def falso(url, body, *, timeout_s):
        enviado.update(body)
        return {"message": {"content": '{"estado": "no", "citas": ["1"]}'},
                "prompt_eval_count": 40, "eval_count": 9}

    ollama._post, original = falso, ollama._post
    try:
        r = ollama.Ollama(modelo="m", num_ctx=4096).generar(Peticion(entrada="p", sistema="s", schema=SCHEMA))
        check(r.salida == {"estado": "no", "citas": ["1"]}, "ollama: salida parseada")
        check(enviado["format"]["additionalProperties"] is False, "ollama: el schema va en `format`")
        check(enviado["messages"][0]["role"] == "system", "ollama: instrucción de sistema")
        check(r.meta == {"input_tokens": 40, "output_tokens": 9}, "ollama: tokens en meta")
        enviado.clear()
        ollama.Ollama(modelo="m").generar(Peticion(entrada="p"))
        check("format" not in enviado, "ollama: sin schema no fuerza formato")
        ollama._post = lambda *a, **k: {"message": {"content": "{}"}, "prompt_eval_count": 4090}
        check(lanza(RespuestaInvalida, lambda: ollama.Ollama(num_ctx=4096).generar(Peticion(entrada="p"))),
              "ollama: si el contador toca num_ctx, se descarta")
        check(lanza(Rechazada, lambda: ollama.Ollama(num_ctx=2048).generar(Peticion(entrada="x" * 10_000))),
              "ollama: lo que no cabe no se envía")
    finally:
        ollama._post = original
    check(ollama.to_json_schema({"type": "OBJECT", "properties": {"a": {"type": "STRING"}}})
          == {"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": False},
          "ollama: dialecto OpenAPI → JSON Schema")
    check(lanza(NoDisponible, lambda: _sin_red(lambda: ollama.Ollama().generar(Peticion(entrada="p")))),
          "ollama: servicio parado → NoDisponible")


def adaptador_gemini() -> None:
    check(lanza(NoDisponible, lambda: gemini.Gemini(api_key="").generar(Peticion(entrada="p"))),
          "gemini: sin clave → NoDisponible")
    peticiones = []

    def urlopen_falso(req, timeout):
        peticiones.append(req)
        cuerpo = {"candidates": [{"content": {"parts": [{"text": '{"estado": "si", "citas": []}'}]}}],
                  "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 5}}
        return _Resp(cuerpo)

    with _urlopen(urlopen_falso):
        r = gemini.Gemini(modelo="g", api_key="clave-falsa").generar(Peticion(entrada="p", schema=SCHEMA))
    req = peticiones[0]
    body = json.loads(req.data)
    check(r.salida == {"estado": "si", "citas": []}, "gemini: salida parseada")
    check("clave-falsa" not in req.full_url and req.get_header("X-goog-api-key") == "clave-falsa",
          "gemini: la clave va en cabecera, no en la URL")
    check(body["generationConfig"]["responseSchema"]["type"] == "OBJECT"
          and "additionalProperties" not in json.dumps(body), "gemini: schema traducido al dialecto OpenAPI")
    check(r.meta["input_tokens"] == 12, "gemini: tokens en meta")
    with _urlopen(lambda req, timeout: _Resp({"candidates": [{"finishReason": "SAFETY"}]})):
        check(lanza(RespuestaInvalida, lambda: gemini.Gemini(api_key="k").generar(Peticion(entrada="p"))),
              "gemini: sin texto → RespuestaInvalida")
    check(gemini.Gemini(api_key="x").sale_de_la_maquina, "gemini: declara que el dato sale")


def adaptador_deep_research() -> None:
    def paso(tipo, texto):
        return types.SimpleNamespace(type=tipo, content=[types.SimpleNamespace(text=texto)])

    class Interacciones:
        def __init__(self, estados):
            self.estados = estados

        def create(self, **kw):
            self.kw = kw
            return types.SimpleNamespace(id="int-1")

        def get(self, id):
            estado = self.estados.pop(0)
            pasos = [paso("model_output", "parte 1"), paso("thought", "no"), paso("model_output", "parte 2")]
            return types.SimpleNamespace(id=id, status=estado, steps=pasos if estado == "completed" else [])

    inter = Interacciones(["in_progress", "in_progress", "completed"])
    esperas = []
    dr = deep_research.DeepResearch(cliente=types.SimpleNamespace(interactions=inter), esperar=esperas.append)
    r = dr.generar(Peticion(entrada="brief"))
    check(r.salida == "parte 1\nparte 2", "deep research: concatena todos los pasos de salida")
    check(len(esperas) == 2 and inter.kw["background"] is True, "deep research: lanza en segundo plano y consulta")
    check(r.meta["interaction_id"] == "int-1", "deep research: el ID queda en meta")
    dr = deep_research.DeepResearch(cliente=types.SimpleNamespace(interactions=Interacciones(["failed"])))
    check(lanza(RespuestaInvalida, lambda: dr.generar(Peticion(entrada="b"))), "deep research: estado failed")
    os.environ.pop("GEMINI_API_KEY", None)
    check(lanza(NoDisponible, lambda: deep_research.DeepResearch().generar(Peticion(entrada="b"))),
          "deep research: sin clave → NoDisponible")


def adaptador_jev(tmp: Path) -> None:
    preguntas = {"q1": {"type": "choice", "criteria": {"a": "A", "b": "B"}}, "q2": {"type": "noul"}}
    check(lanza(NoDisponible, lambda: jev.Jev(api_key="").generar(Peticion(entrada="s", schema=preguntas))),
          "jev: sin clave → NoDisponible")
    ledger._default = ledger.Ledger(tmp / "jev.jsonl")
    jev._post, original = (lambda c, k, t: {"answers": {"q1": {"type": "choice", "choice": "a"},
                                                         "q2": {"type": "noul", "noul": 0.8}},
                                            "usage": {"cost": 0.01}, "model": "typesafe/jev-x"}), jev._post
    try:
        r = llamar(jev.Jev(api_key="k", tope_usd=1.0), Peticion(entrada="s", schema=preguntas), paso="s4")
        check(r.salida["q1"] == {"type": "choice", "choice": "a", "confidence": 0.0, "probabilities": {"a": 0.0}},
              "jev: campos opcionales explícitos")
        check(abs(jev.gasto_acumulado() - 0.01) < 1e-9, "jev: el coste real queda en el ledger")
        check(lanza(Rechazada, lambda: jev.Jev(api_key="k", tope_usd=0.01).generar(Peticion(entrada="s", schema=preguntas))),
              "jev: por encima del tope no se envía")
        check(lanza(Rechazada, lambda: jev.Jev(api_key="k").generar(Peticion(entrada="x" * 40_000, schema=preguntas))),
              "jev: petición demasiado grande no se envía")
        jev._post = lambda c, k, t: {"answers": {"q1": {"type": "choice", "choice": "a"}}}
        check(lanza(RespuestaInvalida, lambda: jev.Jev(api_key="k").generar(Peticion(entrada="s", schema=preguntas))),
              "jev: pregunta sin contestar → RespuestaInvalida")
    finally:
        jev._post = original


def adaptador_whisper(tmp: Path) -> None:
    audio = tmp / "a.wav"
    audio.write_bytes(b"RIFF")
    seg = types.SimpleNamespace
    usado = {}

    class WhisperModel:
        def __init__(self, modelo, device, compute_type):
            usado.update(modelo=modelo, device=device)

        def transcribe(self, ruta, **kw):
            usado.update(kw)
            return iter([seg(start=0.0, end=1.5, text=" Hola ", avg_logprob=-0.2, no_speech_prob=0.1),
                         seg(start=1.5, end=2.0, text=" eh ", avg_logprob=-1.2, no_speech_prob=0.1)]), \
                seg(duration=2.0)

    with _modulos(faster_whisper=types.SimpleNamespace(WhisperModel=WhisperModel)):
        whisper._modelos.clear()
        r = whisper.Whisper(modelo="tiny").generar(Peticion(entrada=str(audio), opciones={"vocabulario": ["K-10"]}))
    check(r.salida["texto"] == "Hola eh" and r.salida["duracion"] == 2.0, "whisper: texto y duración")
    check([s["dudoso"] for s in r.salida["segmentos"]] == [False, True], "whisper: marca segmentos dudosos")
    check(usado["initial_prompt"] == "K-10" and usado["modelo"] == "tiny", "whisper: vocabulario como pista")
    with _modulos(faster_whisper=None):
        whisper._modelos.clear()
        check(lanza(NoDisponible, lambda: whisper.Whisper().generar(Peticion(entrada=str(audio)))),
              "whisper: sin paquete → NoDisponible")


def adaptador_kokoro(tmp: Path) -> None:
    try:
        import numpy as np
    except ImportError:
        print("  skip kokoro: numpy no está instalado")
        return
    escrito = {}

    class KPipeline:
        def __init__(self, lang_code, repo_id):
            self.lang = lang_code

        def __call__(self, texto, voice):
            escrito["voz"] = voice
            yield None, None, np.zeros(12_000)
            yield None, None, np.zeros(12_000)

    soundfile = types.SimpleNamespace(write=lambda ruta, audio, sr: escrito.update(ruta=ruta, n=len(audio), sr=sr))
    with _modulos(kokoro=types.SimpleNamespace(KPipeline=KPipeline), soundfile=soundfile):
        kokoro._pipelines.clear()
        r = kokoro.Kokoro(voz="ef_dora").generar(Peticion(entrada="Hola.", opciones={"salida": str(tmp / "v.wav")}))
    check(escrito["n"] == 24_000 and escrito["sr"] == 24_000 and r.meta["segundos"] == 1.0,
          "kokoro: une los trozos a 24 kHz")
    check(r.salida == tmp / "v.wav" and escrito["voz"] == "ef_dora", "kokoro: devuelve la ruta y usa la voz fijada")
    check(lanza(ValueError, lambda: kokoro.Kokoro().generar(Peticion(entrada="x"))), "kokoro: sin ruta de salida")


def fabrica() -> None:
    os.environ.pop("MOTOR", None)
    check(motores.crear().motor == "stub", "motores: stub por defecto")
    os.environ["MOTOR"] = "ollama"
    check(motores.crear().motor == "ollama", "motores: se elige por MOTOR")
    os.environ.pop("MOTOR")
    check(all(motores.crear(n).motor for n in motores.NOMBRES), "motores: todos se crean sin red ni claves")
    check(lanza(ValueError, lambda: motores.crear("gpt")), "motores: nombre desconocido")


# --- utilidades de los tests ---------------------------------------------------

class _Resp(io.BytesIO):
    def __init__(self, cuerpo: dict):
        super().__init__(json.dumps(cuerpo).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _urlopen:
    def __init__(self, fn):
        self.fn = fn

    def __enter__(self):
        import urllib.request
        self.original, urllib.request.urlopen = urllib.request.urlopen, self.fn

    def __exit__(self, *a):
        import urllib.request
        urllib.request.urlopen = self.original


def _sin_red(fn):
    def rechaza(req, timeout):
        raise urllib.error.URLError("conexión rechazada")
    with _urlopen(rechaza):
        return fn()


class _modulos:
    """Sustituye módulos en sys.modules (None = 'no instalado') y los restaura."""
    def __init__(self, **mods):
        self.mods = mods

    def __enter__(self):
        self.antes = {k: sys.modules.get(k, _AUSENTE) for k in self.mods}
        sys.modules.update(self.mods)

    def __exit__(self, *a):
        for k, v in self.antes.items():
            if v is _AUSENTE:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


_AUSENTE = object()


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    for nombre, prueba in [("contrato y stub", lambda: contrato_y_stub(tmp)), ("ollama", adaptador_ollama),
                           ("gemini", adaptador_gemini), ("deep research", adaptador_deep_research),
                           ("jev", lambda: adaptador_jev(tmp)), ("whisper", lambda: adaptador_whisper(tmp)),
                           ("kokoro", lambda: adaptador_kokoro(tmp)), ("motores", fabrica)]:
        print(f"\n{nombre}")
        prueba()
    print(f"\n{'TODO OK' if fallos == 0 else f'{fallos} fallos'}")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
