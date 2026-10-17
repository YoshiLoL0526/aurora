"""Animaciones declarativas.

Se declara *cómo* cambia un elemento y el núcleo Rust lo interpola en cada frame,
sin volver a llamar a Python:

    card(
        transition=animate.spring(),       # cambios de bg, border_color, opacity y radius
        animate_layout=True,               # se desliza cuando el layout lo mueve
        enter=animate.slide(y=12),         # aparece subiendo y haciéndose visible
        exit=animate.zoom(0.95),           # se va encogiendo y desvaneciéndose
        key=f"tarea-{t.id}",               # identidad estable: imprescindible
    )

Las curvas de tiempo son `spring()` (muelle físico, por defecto) y `tween()`
(duración fija con easing). Los efectos de entrada y salida (`fade`, `slide`,
`zoom` y el general `effect`) dicen desde qué valores aparece un elemento y hacia
cuáles se va: opacidad, desplazamiento y escala. `pulse()` es aparte: un vaivén
perpetuo de opacidad para indicadores de carga, que se pasa en la propiedad
`pulse` de un elemento.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

Easing = Literal["linear", "ease", "ease_in", "ease_out", "ease_in_out"]
_EASINGS = ("linear", "ease", "ease_in", "ease_out", "ease_in_out")


@dataclass(frozen=True, slots=True)
class Spring:
    """Muelle amortiguado: su duración sale de la física y, al cambiar de destino a
    medias, sigue desde donde está. Ver `spring()`."""

    stiffness: float
    damping: float
    mass: float
    delay: float

    def __post_init__(self) -> None:
        if not (self.stiffness > 0 and self.damping > 0 and self.mass > 0):
            raise ValueError("stiffness, damping y mass del muelle deben ser positivos")
        _check_delay(self.delay)


@dataclass(frozen=True, slots=True)
class Tween:
    """Interpolación de duración fija con una curva de easing. Ver `tween()`."""

    duration: float
    easing: Easing
    delay: float

    def __post_init__(self) -> None:
        if not self.duration >= 0:
            raise ValueError("duration no puede ser negativa")
        if self.easing not in _EASINGS:
            raise ValueError(f"easing inválido: {self.easing!r} (usa {', '.join(map(repr, _EASINGS))})")
        _check_delay(self.delay)


@dataclass(frozen=True, slots=True)
class Pulse:
    """Vaivén perpetuo de opacidad (spinners y esqueletos). Ver `pulse()`."""

    duration: float
    delay: float
    floor: float

    def __post_init__(self) -> None:
        if not self.duration > 0:
            raise ValueError("la duración del vaivén debe ser positiva")
        if not 0 < self.floor <= 1:
            raise ValueError("floor del vaivén debe estar entre 0 y 1")
        _check_delay(self.delay)


Transition = Spring | Tween


@dataclass(frozen=True, slots=True)
class Effect:
    """Valores desde los que entra (`enter`) o hacia los que sale (`exit`) un elemento:
    opacidad, desplazamiento en píxeles y escala alrededor de su centro."""

    opacity: float = 1.0
    x: float = 0.0
    y: float = 0.0
    scale: float = 1.0
    transition: Transition | None = None

    def __post_init__(self) -> None:
        values = (self.opacity, self.x, self.y, self.scale)
        if not all(math.isfinite(v) for v in values) or self.scale < 0:
            raise ValueError("los valores del efecto deben ser finitos y la escala no negativa")


def _check_delay(delay: float) -> None:
    if not delay >= 0:
        raise ValueError("delay no puede ser negativo")


def spring(
    *, stiffness: float = 380.0, damping: float = 30.0, mass: float = 1.0, delay: float = 0.0
) -> Spring:
    """Muelle físico. Más `stiffness`, más rápido; menos `damping`, más rebote.

    Los valores por defecto dan una animación ágil (~0,3 s) con un rebote apenas
    visible. `delay` (segundos) retrasa el comienzo: útil para escalonar listas.
    """
    return Spring(float(stiffness), float(damping), float(mass), float(delay))


def tween(duration: float = 0.25, *, easing: Easing = "ease_out", delay: float = 0.0) -> Tween:
    """Interpolación de `duration` segundos con una curva de easing de CSS."""
    return Tween(float(duration), easing, float(delay))


def pulse(duration: float = 1.0, *, delay: float = 0.0, floor: float = 0.35) -> Pulse:
    """Vaivén perpetuo de opacidad: baja de 1 a `floor` y vuelve, sin terminar.

    Es para indicadores de carga (spinners, esqueletos), no para transiciones:
    se pasa en la propiedad `pulse` de un elemento. `delay` permite escalonar
    varios elementos (p. ej. los puntos de un spinner) y `floor` la opacidad
    mínima del vaivén.
    """
    return Pulse(float(duration), float(delay), float(floor))


def effect(
    *,
    opacity: float = 1.0,
    x: float = 0.0,
    y: float = 0.0,
    scale: float = 1.0,
    transition: Transition | None = None,
) -> Effect:
    """Efecto general de entrada o salida. Sin `transition` usa la del elemento."""
    return Effect(float(opacity), float(x), float(y), float(scale), transition)


def fade(opacity: float = 0.0, *, transition: Transition | None = None) -> Effect:
    """Aparece desde (o se va hacia) la opacidad dada."""
    return effect(opacity=opacity, transition=transition)


def slide(
    x: float = 0.0, y: float = 0.0, *, fade: bool = True, transition: Transition | None = None
) -> Effect:
    """Aparece desde (o se va hacia) un desplazamiento, por defecto desvaneciéndose."""
    return effect(opacity=0.0 if fade else 1.0, x=x, y=y, transition=transition)


def zoom(scale: float = 0.9, *, fade: bool = True, transition: Transition | None = None) -> Effect:
    """Aparece desde (o se va hacia) una escala, por defecto desvaneciéndose."""
    return effect(opacity=0.0 if fade else 1.0, scale=scale, transition=transition)


__all__ = [
    "Easing",
    "Effect",
    "Pulse",
    "Spring",
    "Transition",
    "Tween",
    "effect",
    "fade",
    "pulse",
    "slide",
    "spring",
    "tween",
    "zoom",
]
