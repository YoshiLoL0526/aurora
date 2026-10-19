"""Controles de formulario: campos, casillas, interruptores, radio y deslizador."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .. import _motion as motion
from .. import animate
from .._icons import _ARROW_DOWN, _ARROW_UP, _CHECK
from ..elements import Element, TextLike, box, column, image, row, text
from ..signal import Signal
from ._shared import _INPUT_STYLE, Options, _a11y_label, _field, _items, _toggle
from ._state import _DRAFTS, _DRAG_START


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
    label_props = _a11y_label(label)
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
    return row(
        **{
            "gap": 8,
            "align": "center",
            "radius": 6,
            "key": key,
            "on_click": flip,
            "role": "checkbox",
            "checked": on,
            **label_props,
            **style,
        }
    )[mark, label is not None and text(label, hidden=bool(label_props))]


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
    label_props = _a11y_label(label)
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
    return row(
        **{
            "gap": 10,
            "align": "center",
            "radius": 10,
            "key": key,
            "on_click": flip,
            "role": "switch",
            "checked": value,
            **label_props,
            **style,
        }
    )[track, label is not None and text(label, hidden=bool(label_props))]


def radio(options: Options, selected: Signal[Any], *, key: str | None = None, **style: Any) -> Element:
    """Grupo de botones de opción: uno activo a la vez.

    `options` son valores (o pares `(valor, etiqueta)`) y `selected`, el `Signal`
    con el valor activo. Cada fila (círculo y etiqueta) se activa con clic, Enter
    o Espacio y tiene la key `f"{key}-{valor}"`. El punto interior entra
    encogiéndose, como la marca de un `checkbox`.
    """
    items = _items(options)
    base = key or f"radio-{id(selected)}"

    def option(index: int, value: Any, label: str) -> Element:
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
            role="radio",
            checked=on,
            label=label,
            position_in_set=index + 1,
            set_size=len(items),
            on_click=lambda v=value: selected.set(v),
        )[circle, text(label, transition=motion.fast(), hidden=True)]

    return column(**{"gap": 10, "role": "radiogroup", **style})[
        [option(i, v, label) for i, (v, label) in enumerate(items)]
    ]


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

    # Paso del teclado y de las acciones Incrementar/Decrementar del lector.
    step = span / 20.0

    def on_key(e: Any) -> bool | None:
        if e.key in ("ArrowRight", "ArrowUp"):
            set_value(current + step)
            return True
        if e.key in ("ArrowLeft", "ArrowDown"):
            set_value(current - step)
            return True
        if e.key == "Home":
            set_value(low)
            return True
        if e.key == "End":
            set_value(high)
            return True
        return None

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
        on_key=on_key,
        on_value=set_value,
        role="slider",
        value=current,
        value_min=low,
        value_max=high,
        value_step=step,
        **{
            "width": width,
            "height": 24,
            "padding": (0, 8),
            "justify": "center",
            "cursor": "pointer",
            "focusable": True,
            **style,
        },
    )[rail]


def _decimals(step: float) -> int:
    """Decimales que hacen falta para mostrar múltiplos de `step` (`0.25` → 2)."""
    text = f"{step:.10f}".rstrip("0")
    return len(text.split(".")[1]) if "." in text else 0


def number_input(
    value: Signal[float] | Signal[int],
    *,
    min: float | None = None,
    max: float | None = None,
    step: float = 1,
    decimals: int | None = None,
    on_change: Callable[[float], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Campo numérico: se escribe el número o se ajusta con ↑/↓ y sus flechas.

    `value` se recorta a `[min, max]`. Con `step` entero y un valor entero el
    campo trabaja con `int`; si no, con `float` redondeado a `decimals` (por
    defecto, los de `step`: `0.25` → 2). Mientras se escribe, cada número válido
    y dentro del rango se asigna al momento; un texto a medias (`"-"`, `"1,"`) o
    fuera del rango espera, y al salir del campo o pulsar Enter se recorta al
    rango o vuelve al último valor válido. La coma vale como separador decimal.
    `on_change(valor)` se llama con cada valor nuevo.
    """
    if min is not None and max is not None and max < min:
        raise ValueError("max debe ser mayor o igual que min")
    if step <= 0:
        raise ValueError("step debe ser positivo")
    k = key or f"number-{id(value)}"
    draft = _DRAFTS.setdefault(k, Signal(None))
    current = value()
    integer = isinstance(step, int) and isinstance(current, int) and decimals in (None, 0)
    places = 0 if integer else (decimals if decimals is not None else _decimals(step))

    def clamp(v: float) -> float:
        if min is not None and v < min:
            v = min
        if max is not None and v > max:
            v = max
        return round(v) if integer else round(float(v), places)

    def fmt(v: float) -> str:
        return str(int(v)) if integer else f"{v:.{places}f}"

    def parse(raw: str) -> float | None:
        try:
            v = float(raw.strip().replace(",", "."))
        except ValueError:
            return None
        if v != v or v in (float("inf"), float("-inf")):
            return None
        if integer:
            return int(v) if v.is_integer() else None
        return v

    def commit(v: float) -> None:
        v = clamp(v)
        if v != value():
            value.set(v)  # ty: ignore[invalid-argument-type]
            if on_change is not None:
                on_change(v)

    def typed(raw: str) -> None:
        draft.set(raw)
        v = parse(raw)
        if v is not None and clamp(v) == v:
            commit(v)

    def settle(*_: Any) -> None:
        raw = draft()
        if raw is not None:
            v = parse(raw)
            if v is not None:
                commit(v)
            draft.set(None)

    def nudge(direction: int) -> None:
        draft.set(None)
        commit(value() + direction * step)

    def on_key(e: Any) -> bool | None:
        if e.key in ("ArrowUp", "ArrowDown"):
            nudge(1 if e.key == "ArrowUp" else -1)
            return True
        return None

    can_up = max is None or current < max
    can_down = min is None or current > min

    def arrow(icon: bytes, direction: int, enabled: bool) -> Element:
        return box(
            key=f"{k}-{'up' if direction > 0 else 'down'}",
            grow=1,
            width=24,
            align="center",
            justify="center",
            radius=6,
            opacity=1.0 if enabled else 0.35,
            focusable=False,
            hidden=True,
            **({"bg_hover": "$surface_hover", "on_click": lambda: nudge(direction)} if enabled else {}),
        )[image(icon, width=12)]

    shown = draft() if draft() is not None else fmt(current)
    a11y_range = {name: v for name, v in (("value_min", min), ("value_max", max)) if v is not None}
    field = Element(
        "input",
        content=shown,
        key=f"{k}-field",
        grow=1,
        min_width=0,
        on_change=typed,
        on_submit=settle,
        on_blur=settle,
        on_key=on_key,
        role="spinbutton",
        value_step=step,
        padding=(6, 0),
        **a11y_range,
    )
    styles = {**_INPUT_STYLE, "padding": (3, 4, 3, 12), "gap": 4, "align": "center", "width": 140}
    return row(**{**styles, "key": k, **style})[
        field,
        column(gap=1, height=34)[arrow(_ARROW_UP, 1, can_up), arrow(_ARROW_DOWN, -1, can_down)],
    ]
