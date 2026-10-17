"""Controles de formulario: campos, casillas, interruptores, radio y deslizador."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .. import _motion as motion
from .. import animate
from .._icons import _CHECK
from ..elements import Element, TextLike, box, column, image, row, text
from ..signal import Signal
from ._shared import Options, _field, _items, _toggle
from ._state import _DRAG_START


def text_input(
    value: Signal[str] | TextLike,
    *,
    placeholder: str = "",
    on_change: Callable[[str], Any] | None = None,
    on_submit: Callable[[str], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Campo de texto de una línea.

    Con un `Signal[str]` queda enlazado en los dos sentidos: lo que se escribe
    actualiza el Signal y lo que se asigna al Signal aparece en el campo.
    `on_submit(texto)` se llama al pulsar Enter.
    """
    return _field(value, on_change, on_submit, key, {"placeholder": placeholder, **style})


def textarea(
    value: Signal[str] | TextLike,
    *,
    placeholder: str = "",
    rows: int = 3,
    on_change: Callable[[str], Any] | None = None,
    on_submit: Callable[[str], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Campo de texto multilínea. Crece con el contenido (mínimo `rows` líneas).

    Enter inserta un salto de línea; Ctrl+Enter (Cmd+Enter en macOS) llama a
    `on_submit(texto)`.
    """
    styles = {"placeholder": placeholder, "multiline": True, "rows": rows, "padding": (10, 12), **style}
    return _field(value, on_change, on_submit, key, styles)


def field(
    control: Element,
    *,
    label: str | None = None,
    hint: str | None = None,
    error: str | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Campo de formulario: etiqueta, control y mensaje de ayuda o error.

    `error` sustituye a `hint` en color de peligro (`$danger`): pásalo con el
    texto del problema y quítalo cuando el valor sea válido. Los `estilo` van a
    la columna (`gap`, `width`, `grow`…).
    """
    message = error if error else hint
    return column(**{"gap": 6, "key": key, **style})[
        label is not None and text(label, size=12, weight=600),
        control,
        message is not None and text(message, size=11, color="$danger" if error else "$muted"),
    ]


def checkbox(
    checked: Signal[bool] | bool,
    label: TextLike | None = None,
    *,
    on_change: Callable[[bool], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Casilla de verificación. Con un `Signal[bool]` se enlaza sola; `on_change(valor)`
    se llama en cada cambio. Se activa con clic, Enter o Espacio.

    La caja funde su color y la marca entra encogiéndose; con `App(motion=False)`
    (o `AURORA_MOTION=0`) el cambio es inmediato.
    """
    on, flip = _toggle(checked, on_change)
    mark = box(
        width=18,
        height=18,
        radius=5,
        align="center",
        justify="center",
        shrink=0,
        bg="$primary" if on else "$surface",
        border_width=1.5,
        border_color="$primary" if on else "$muted",
        transition=motion.fast(),
    )[
        on
        and image(
            _CHECK,
            width=12,
            enter=motion.entering(animate.zoom(0.55)),
            exit=motion.leaving(animate.zoom(0.55)),
        )
    ]
    return row(**{"gap": 8, "align": "center", "radius": 6, "key": key, "on_click": flip, **style})[
        mark, label is not None and text(label)
    ]


def switch(
    on: Signal[bool] | bool,
    label: TextLike | None = None,
    *,
    on_change: Callable[[bool], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Interruptor encendido/apagado. Igual que `checkbox`, con otra forma.

    El knob se desliza y el fondo funde su color al cambiar; con `App(motion=False)`
    (o `AURORA_MOTION=0`) el cambio es inmediato.
    """
    value, flip = _toggle(on, on_change)
    track = box(
        width=36,
        height=20,
        radius="$full",
        shrink=0,
        bg="$primary" if value else "$border",
        transition=motion.fast(),
    )[
        box(
            position="absolute",
            top=2,
            left=18 if value else 2,
            width=16,
            height=16,
            radius="$full",
            bg="#FFFFFF",
            shadow=(0, 1, 3, "#00000040"),
            animate_layout=motion.move(),
        )
    ]
    return row(**{"gap": 10, "align": "center", "radius": 10, "key": key, "on_click": flip, **style})[
        track, label is not None and text(label)
    ]


def radio(options: Options, selected: Signal[Any], *, key: str | None = None, **style: Any) -> Element:
    """Grupo de botones de opción: uno activo a la vez.

    `options` son valores (o pares `(valor, etiqueta)`) y `selected`, el `Signal`
    con el valor activo. Cada fila (círculo y etiqueta) se activa con clic, Enter
    o Espacio y tiene la key `f"{key}-{valor}"`. El punto interior entra
    encogiéndose, como la marca de un `checkbox`.
    """
    items = _items(options)
    base = key or f"radio-{id(selected)}"

    def option(value: Any, label: str) -> Element:
        on = selected() == value
        circle = box(
            width=18,
            height=18,
            radius="$full",
            align="center",
            justify="center",
            shrink=0,
            bg="$primary" if on else "$surface",
            border_width=1.5,
            border_color="$primary" if on else "$muted",
            transition=motion.fast(),
        )[
            on
            and box(
                width=7,
                height=7,
                radius="$full",
                bg="#FFFFFF",
                enter=motion.entering(animate.zoom(0.4)),
                exit=motion.leaving(animate.zoom(0.4)),
            )
        ]
        return row(
            key=f"{base}-{value}",
            gap=8,
            align="center",
            radius=6,
            on_click=lambda v=value: selected.set(v),
        )[circle, text(label, transition=motion.fast())]

    return column(**{"gap": 10, **style})[[option(v, label) for v, label in items]]


def slider(
    value: Signal[float],
    *,
    min: float = 0.0,
    max: float = 1.0,
    width: float = 180,
    on_change: Callable[[float], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Deslizador horizontal: arrastra el pulgar para cambiar `value`.

    `value` va de `min` a `max` y se recorta a ese rango; `width` fija el ancho
    en píxeles (el arrastre se calcula con él: no lo pongas en `%`).
    `on_change(valor)` se llama en cada paso del arrastre. El pulgar y el
    relleno siguen el valor con el movimiento común (con `App(motion=False)`, al
    instante).
    """
    if max <= min:
        raise ValueError("max debe ser mayor que min")
    low, high = float(min), float(max)
    current = float(value())
    current = low if current < low else high if current > high else current
    span = high - low
    t = (current - low) / span
    travel = float(width) - 16.0
    k = key or f"slider-{id(value)}"

    def set_value(v: float) -> None:
        v = low if v < low else high if v > high else v
        value.set(v)
        if on_change is not None:
            on_change(v)

    def on_drag(e: Any) -> None:
        if e.phase == "start":
            _DRAG_START[k] = float(value())
            return
        start = _DRAG_START.get(k)
        if start is None:
            return
        set_value(start + e.dx / travel * span)
        if e.phase == "end":
            _DRAG_START.pop(k, None)

    fill = box(
        position="absolute",
        left=0,
        top=0,
        bottom=0,
        width=f"{t * 100:.4f}%",
        radius="$full",
        bg="$primary",
        animate_layout=motion.move(),
    )
    # Punto de anclaje sin ancho: su centro viaja por el carril y el pulgar cuelga
    # de él centrado (16 x 16), así no se sale por los extremos.
    anchor = box(
        position="absolute", left=f"{t * 100:.4f}%", top=0, bottom=0, width=0, animate_layout=motion.move()
    )[
        box(
            position="absolute",
            left=-8,
            top=-5,
            width=16,
            height=16,
            radius="$full",
            bg="#FFFFFF",
            border_width=2,
            border_color="$primary",
            shadow=(0, 1, 4, "#00000066"),
        )
    ]
    rail = box(width="100%", height=6, radius="$full", bg="$surface_hover", key=f"{k}-rail")[fill, anchor]
    return box(
        key=key,
        on_drag=on_drag,
        **{
            "width": width,
            "height": 24,
            "padding": (0, 8),
            "justify": "center",
            "cursor": "pointer",
            **style,
        },
    )[rail]
