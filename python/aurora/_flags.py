"""Interruptores del entorno: `AURORA_INSPECTOR`, `AURORA_RELOAD` y `AURORA_MOTION`."""

from __future__ import annotations

import os

_ON = ("1", "true", "yes", "on")
_OFF = ("0", "false", "no", "off")


def enabled(flag: bool | None, name: str, *, default: bool = False) -> bool:
    """`flag` si se indica; si no, lo que diga la variable de entorno `name`.

    `1`, `true`, `yes` y `on` activan; `0`, `false`, `no` y `off` desactivan.
    Con la variable ausente o con un texto que no reconoce, el valor es `default`.
    """
    if flag is not None:
        return bool(flag)
    value = os.environ.get(name, "").strip().lower()
    if value in _ON:
        return True
    if value in _OFF:
        return False
    return default
