"""Mecánica compartida por los desplegables (`menu` y `select`).

Los dos se abren sobre el resto de la vista con la misma receta: un fondo
invisible que cierra al hacer clic fuera, un panel anclado con la entrada y la
salida animadas, y Esc (o Enter, en el `select`) para cerrarlos.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .. import _motion as motion
from .. import animate
from ..elements import Element, box
from ..signal import Signal
from ._state import _OPEN


def open_signal(key: str) -> Signal[bool]:
    """El `Signal` abierto/cerrado de `key` (uno por key, conservado entre reconstrucciones)."""
    return _OPEN.setdefault(key, Signal(False))


def toggle(open_: Signal[bool]) -> Callable[[], None]:
    """Acción del disparador: abre el desplegable si está cerrado y viceversa."""

    def flip() -> None:
        open_.set(not open_())

    return flip


def close_on_key(event: Any, open_: Signal[bool], *combos: str) -> bool | None:
    """Cierra el desplegable abierto si la tecla es una de las combinaciones
    (`"escape"`, `"enter"`…); devuelve `True` si la consumió, para el `on_key`."""
    if open_() and any(event.matches(combo) for combo in combos):
        open_.set(False)
        return True
    return None


def backdrop(close: Callable[[], Any]) -> Element:
    """Fondo invisible (mucho mayor que la ventana) que cierra el desplegable al hacer clic fuera."""
    return box(
        layer="overlay",
        position="absolute",
        left=-10_000,
        top=-10_000,
        width=20_000,
        height=20_000,
        focusable=False,
        on_click=close,
    )


def panel(*, top: float, content: Element, **style: Any) -> Element:
    """Panel del desplegable: por encima del resto (`layer="overlay"`), anclado a `top`,
    con la animación de entrada/salida común. Los `style` extra ajustan el anclaje
    (`min_width`, `right`…)."""
    return box(
        layer="overlay",
        position="absolute",
        top=top,
        left=0,
        padding=4,
        radius="$md",
        bg="$surface",
        border_width=1,
        border_color="$border",
        shadow=(0, 12, 32, "$shadow"),
        enter=motion.entering(animate.slide(y=-6)),
        exit=motion.leaving(animate.fade()),
        **style,
    )[content]
