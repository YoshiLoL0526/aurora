"""Mecánica compartida por lo que se abre sobre la vista anclado a un disparador
(`menu`, `select`, `combobox`, `date_picker`, `popover`…).

Todos siguen la misma receta: un fondo invisible que cierra al hacer clic fuera,
un panel anclado (que se vuelca si no cabe) con la entrada y la salida animadas,
y Esc (o Enter, en los selectores) para cerrarlos.
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


def panel(
    *,
    content: Element,
    top: float | None = None,
    placement: str = "bottom-start",
    offset: float = 6,
    **style: Any,
) -> Element:
    """Panel del desplegable: por encima del resto (`layer="overlay"`), con la
    animación de entrada/salida común.

    Se ancla al disparador (el hermano anterior en el flujo): el núcleo lo
    coloca en el lado de `placement` (`"bottom-start"`, `"top-end"`, `"right"`…)
    a `offset` píxeles, lo vuelca al lado opuesto si no cabe y lo desplaza lo
    justo para no salirse de la ventana. Con `top` se fija en cambio a esa
    distancia del borde superior del contenedor, sin volcarse. Los `style` extra
    ajustan el panel (`min_width`, `width="100%"` para igualar al disparador…).
    """
    anchor: dict[str, Any] = (
        {"top": top, "left": 0} if top is not None else {"placement": placement, "offset": offset}
    )
    props: dict[str, Any] = {
        "layer": "overlay",
        "position": "absolute",
        **anchor,
        "padding": 4,
        "radius": "$md",
        "bg": "$surface",
        "border_width": 1,
        "border_color": "$border",
        "shadow": (0, 12, 32, "$shadow"),
        "enter": motion.entering(animate.slide(y=-6)),
        "exit": motion.leaving(animate.fade()),
        **style,
    }
    return box(**props)[content]
