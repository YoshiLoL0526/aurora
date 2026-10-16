"""Rutas de los recursos de la app que funcionan igual con Python y empaquetadas."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resource(path: str | os.PathLike[str]) -> str:
    """Ruta absoluta de un recurso de la app (imagen, datos, …).

    Una ruta relativa se resuelve desde la carpeta del script principal, no desde el directorio
    de trabajo; dentro de un ejecutable de `aurora build`, desde la carpeta donde quedan los
    recursos incluidos (`include`), que conserva la misma estructura. Así
    `image(resource("assets/logo.png"))` funciona igual al ejecutar con Python, al hacer doble
    clic en el ejecutable o al lanzarlo desde otra carpeta. Una ruta absoluta se devuelve tal cual.
    """
    target = Path(path)
    if target.is_absolute():
        return str(target)
    return str(_base() / target)


def _base() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)  # PyInstaller: donde se extraen los recursos
    if bundle:
        return Path(bundle)
    main = getattr(sys.modules.get("__main__"), "__file__", None)
    return Path(main).resolve().parent if main else Path.cwd()
