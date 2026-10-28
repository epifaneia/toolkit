"""kokoro — texto a voz, en local, con Kokoro-82M.

    Peticion.entrada  → el texto a leer
    Peticion.opciones → salida: ruta del .wav (obligatoria); voz: para
                        cambiar la de por defecto en una sola petición
    Respuesta.salida  → la ruta del .wav escrito (24 kHz, mono)
    Respuesta.meta    → segundos de audio

La voz va fijada por configuración: un pipeline que cambia de voz entre
ejecuciones no se puede comparar consigo mismo.

Configuración por entorno: KOKORO_VOZ, KOKORO_IDIOMA ("e" = español).
Necesita `pip install kokoro soundfile` (y torch). Kokoro carga sus pesos de
Hugging Face la primera vez.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contrato import NoDisponible, Peticion, Respuesta

SR = 24_000
_pipelines: dict[str, Any] = {}


@dataclass
class Kokoro:
    voz: str = field(default_factory=lambda: os.environ.get("KOKORO_VOZ", "").strip() or "ef_dora")
    idioma: str = field(default_factory=lambda: os.environ.get("KOKORO_IDIOMA", "").strip() or "e")
    modelo: str = "hexgrad/Kokoro-82M"
    motor: str = "kokoro"
    endpoint: str = "local"
    sale_de_la_maquina: bool = False

    def generar(self, peticion: Peticion) -> Respuesta:
        if not peticion.opciones.get("salida"):
            raise ValueError("Kokoro necesita opciones={'salida': ruta del .wav}")
        salida = Path(peticion.opciones["salida"])
        voz = peticion.opciones.get("voz", self.voz)
        try:
            import numpy as np
            import soundfile as sf
        except ImportError as e:
            raise NoDisponible("Falta numpy o soundfile: pip install kokoro soundfile") from e
        trozos = [np.asarray(audio) for _, _, audio in self._cargar()(peticion.entrada, voice=voz)]
        audio = np.concatenate(trozos).astype(np.float32)
        salida.parent.mkdir(parents=True, exist_ok=True)
        sf.write(salida, audio, SR)
        return Respuesta(salida=salida, motor=self.motor, modelo=self.modelo,
                         meta={"voz": voz, "segundos": round(len(audio) / SR, 2)})

    def _cargar(self) -> Any:
        if self.idioma not in _pipelines:
            try:
                from kokoro import KPipeline
            except ImportError as e:
                raise NoDisponible("Falta kokoro: pip install kokoro soundfile") from e
            _pipelines[self.idioma] = KPipeline(lang_code=self.idioma, repo_id=self.modelo)
        return _pipelines[self.idioma]
