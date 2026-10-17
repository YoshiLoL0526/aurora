"""Escala de movimiento de los componentes y su interruptor global.

Los componentes declaran sus animaciones con estas curvas, pensadas como una
escala coherente: fundidos cortos para colores, deslizamientos algo más largos,
y entradas/salidas de superposiciones (la salida, más rápida que la entrada).

`App(view, motion=False)` o `AURORA_MOTION=0` las desactivan: los componentes
saltan al estado nuevo sin transición (útil para tests de snapshot y para quien
prefiera que nada se mueva).
"""

from __future__ import annotations

import os
from dataclasses import replace

from . import animate
from .animate import Effect, Transition, tween

# Fundidos de color y opacidad en controles (checkbox, subrayado de tabs).
FAST = tween(0.12, easing="ease_out")
# Deslizamientos cortos dentro de un control (el knob de un switch).
MOVE = tween(0.18, easing="ease_out")
# Aparición de superposiciones (menú del select, modales, toasts).
ENTER = tween(0.18, easing="ease_out")
# Desaparición: más rápida que la entrada.
EXIT = tween(0.12, easing="ease_in")

_active = True


def enabled(motion: bool | None) -> bool:
    """`motion` si se indica; si no, la variable de entorno `AURORA_MOTION`
    (`0`, `false`, `no` u `off` la desactivan). Por defecto, activo."""
    if motion is not None:
        return bool(motion)
    return os.environ.get("AURORA_MOTION", "").strip().lower() not in ("0", "false", "no", "off")


def activate(on: bool) -> bool:
    """Activa o desactiva el movimiento y devuelve el valor anterior."""
    global _active
    previous = _active
    _active = on
    return previous


def fast() -> Transition | None:
    """Transición de colores y opacidad, o `None` con el movimiento apagado."""
    return FAST if _active else None


def move() -> Transition | None:
    """Transición de deslizamientos cortos, o `None` con el movimiento apagado."""
    return MOVE if _active else None


def pulse(duration: float = 1.0, *, delay: float = 0.0, floor: float = 0.35) -> animate.Pulse | None:
    """Vaivén perpetuo de opacidad, o `None` con el movimiento apagado."""
    return animate.pulse(duration, delay=delay, floor=floor) if _active else None


def entering(effect: Effect) -> Effect | None:
    """El efecto de entrada con la curva común, o `None` si está apagado."""
    return replace(effect, transition=ENTER) if _active else None


def leaving(effect: Effect) -> Effect | None:
    """El efecto de salida con la curva común, o `None` si está apagado."""
    return replace(effect, transition=EXIT) if _active else None
