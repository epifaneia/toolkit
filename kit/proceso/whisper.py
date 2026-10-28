"""whisper — voz a texto, en local, con faster-whisper.

    Peticion.entrada  → ruta del audio
    Peticion.opciones → vocabulario: lista de términos que el modelo debe
                        reconocer (nombres propios, siglas); va como pista
    Respuesta.salida  → {"texto": str, "duracion": s,
                         "segmentos": [{"inicio", "fin", "texto", "dudoso"}]}

Un segmento es `dudoso` cuando el modelo duda de lo que oyó (logprob medio
bajo) o cree que no había voz: el paso 5 decide qué hacer con él, este
adaptador no lo corrige ni lo descarta.

Un modelo de voz es una llamada a un modelo aunque el pipeline la use para
preparar la entrada, así que pasa por el mismo contrato y el mismo ledger.

Configuración por entorno: WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE.
Necesita `pip install faster-whisper`. El modelo se descarga la primera vez.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contrato import NoDisponible, Peticion, Respuesta

_modelos: dict[tuple, Any] = {}     # cargar un modelo cuesta segundos: uno por configuración


@dataclass
class Whisper:
    modelo: str = field(default_factory=lambda: os.environ.get("WHISPER_MODEL", "").strip() or "large-v3-turbo")
    dispositivo: str = field(default_factory=lambda: os.environ.get("WHISPER_DEVICE", "").strip() or "cpu")
    computo: str = field(default_factory=lambda: os.environ.get("WHISPER_COMPUTE", "").strip() or "int8")
    idioma: str = "es"
    motor: str = "faster-whisper"
    endpoint: str = "local"
    sale_de_la_maquina: bool = False

    def generar(self, peticion: Peticion) -> Respuesta:
        audio = Path(peticion.entrada)
        if not audio.is_file():
            raise FileNotFoundError(f"Audio no encontrado: {audio}")
        vocabulario = peticion.opciones.get("vocabulario") or []
        segmentos, info = self._cargar().transcribe(
            str(audio), language=self.idioma, vad_filter=True, beam_size=5,
            condition_on_previous_text=False,
            initial_prompt=", ".join(vocabulario) or None,
        )
        filas = [{"inicio": round(s.start, 2), "fin": round(s.end, 2), "texto": s.text.strip(),
                  "dudoso": s.avg_logprob < -0.7 or s.no_speech_prob > 0.5} for s in segmentos]
        salida = {"texto": " ".join(f["texto"] for f in filas).strip(),
                  "duracion": round(float(info.duration or 0.0), 2), "segmentos": filas}
        return Respuesta(salida=salida, motor=self.motor, modelo=self.modelo)

    def _cargar(self) -> Any:
        clave = (self.modelo, self.dispositivo, self.computo)
        if clave not in _modelos:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise NoDisponible("Falta faster-whisper: pip install faster-whisper") from e
            _modelos[clave] = WhisperModel(self.modelo, device=self.dispositivo, compute_type=self.computo)
        return _modelos[clave]
