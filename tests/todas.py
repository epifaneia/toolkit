"""Todas las pruebas locales. Sin red, sin claves, sin modelos.

    python tests/todas.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PRUEBAS = ["test_custodia.py", "test_proceso.py", "test_montaje.py", "test_guardarrail_out.py"]


def main() -> int:
    fallidas = [p for p in PRUEBAS if subprocess.run([sys.executable, str(AQUI / p)], capture_output=True).returncode]
    for p in PRUEBAS:
        print(f"{'FAIL' if p in fallidas else 'ok  '} {p}")
    return 1 if fallidas else 0


if __name__ == "__main__":
    raise SystemExit(main())
