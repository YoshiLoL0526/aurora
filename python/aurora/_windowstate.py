"""Recordar entre sesiones el tamaño, la posición y si estaba maximizada cada ventana.

`App(remember="mi-app")` guarda el estado en `<config>/mi-app/window-state.json`,
donde `<config>` es el directorio de configuración del usuario (`%APPDATA%` en
Windows, `~/Library/Application Support` en macOS y `$XDG_CONFIG_HOME` o
`~/.config` en Linux). El archivo es un dict por ventana: `"main"` para la
principal y la clave `remember` de cada `app.window(...)` para las demás.

Guardar o leer nunca rompe la app: un archivo ilegible se ignora y un error al
escribir se avisa por stderr.
"""

from __future__ import annotations

import math
import os
import re
import sys
from pathlib import Path
from typing import Any

FILE = "window-state.json"
MAIN = "main"
_NAME = re.compile(r"\w[\w .-]*")


def check_name(name: object) -> str:
    """Valida el nombre de la carpeta de `App(remember=...)`."""
    if not isinstance(name, str) or not _NAME.fullmatch(name) or name.endswith((".", " ")):
        raise ValueError(
            "`remember` debe ser un nombre de carpeta (letras, números, espacios, '.', '-' o '_'); "
            f"llegó {name!r}"
        )
    return name


def check_key(key: object) -> str:
    """Valida la clave `remember` de una ventana adicional."""
    if not isinstance(key, str) or not key.strip():
        raise ValueError(f"`remember` debe ser un texto no vacío; llegó {key!r}")
    if key == MAIN:
        raise ValueError(f"`remember={MAIN!r}` está reservado para la ventana principal")
    return key


def config_dir() -> Path:
    """El directorio de configuración del usuario, según el sistema."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        return Path(base) if base else Path.home() / "AppData" / "Roaming"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    base = os.environ.get("XDG_CONFIG_HOME")
    return Path(base) if base else Path.home() / ".config"


def path(name: str) -> Path:
    """El archivo donde se recuerda el estado de las ventanas de `name`."""
    return config_dir() / name / FILE


def load(name: str) -> dict[str, Any]:
    """Todo lo recordado de `name` (vacío si no hay nada o no se puede leer)."""
    try:
        import json  # solo con `remember`: importarlo alarga el arranque

        data = json.loads(path(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(name: str, key: str, state: dict[str, Any]) -> None:
    """Recuerda el estado de la ventana `key` (sin tocar el de las demás)."""
    import json

    target = path(name)
    data = load(name)
    data[key] = state
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temp, target)
    except OSError as e:
        print(f"aurora: no se pudo recordar el estado de la ventana: {e}", file=sys.stderr)


def _pair(value: object, *, positive: bool) -> tuple[float, float] | None:
    if not isinstance(value, list | tuple) or len(value) != 2:
        return None
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in value):
        return None
    a, b = float(value[0]), float(value[1])
    if not (math.isfinite(a) and math.isfinite(b)) or (positive and (a <= 0 or b <= 0)):
        return None
    return a, b


def restore(entry: object) -> tuple[tuple[float, float] | None, tuple[float, float] | None, bool]:
    """`(size, position, maximized)` de una entrada recordada; lo inválido sale `None`/`False`."""
    if not isinstance(entry, dict):
        return None, None, False
    size = _pair(entry.get("size"), positive=True)
    position = _pair(entry.get("position"), positive=False)
    return size, position, entry.get("maximized") is True
