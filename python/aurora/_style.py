"""Las propiedades de estilo y los manejadores que admiten los elementos.

`Style` es la fuente de verdad: de sus claves salen las que `Element` acepta
(cualquier otra lanza `TypeError` con una sugerencia) y es lo que anota los
`**estilo` de las primitivas y los componentes, para que el tipado y el editor
las conozcan. Las claves de estilo deben coincidir con las que lee
`spec::parse` (`KEYS` en `src/spec.rs`) y los eventos con los que despacha el
núcleo: `tests/test_validation.py` lo comprueba.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Literal, TypedDict, TypeVar

_T = TypeVar("_T")

# Toda propiedad admite también una función sin argumentos (una región reactiva)
# y `None` (como si no se pasara).
Prop = _T | Callable[[], _T] | None

Color = str
Length = float | str
Edges = float | tuple[float, float] | tuple[float, float, float, float]
Handler = Callable[..., Any] | None
Align = Literal["start", "center", "end", "baseline", "stretch"]
Justify = Literal["start", "center", "end", "between", "around", "evenly"]
Cursor = Literal[
    "default",
    "pointer",
    "text",
    "grab",
    "grabbing",
    "col-resize",
    "row-resize",
    "ns-resize",
    "ew-resize",
    "nesw-resize",
    "nwse-resize",
    "crosshair",
]
WindowDrag = Literal["move", "n", "s", "e", "w", "ne", "nw", "se", "sw"]


class Style(TypedDict, total=False):
    """Propiedades de estilo, de accesibilidad y manejadores de un elemento.

    Sirve para anotar funciones propias que reenvían el estilo a Aurora:
    `def panel(**estilo: Unpack[Style]) -> Element: return card(**estilo)`.
    """

    # Identidad (no es estilo: `Element` la recibe aparte)
    key: str | None
    # Layout
    direction: Prop[Literal["row", "column"]]
    gap: Prop[float]
    padding: Prop[Edges]
    align: Prop[Align]
    justify: Prop[Justify]
    width: Prop[Length]
    height: Prop[Length]
    min_width: Prop[float]
    max_width: Prop[float]
    min_height: Prop[float]
    max_height: Prop[float]
    grow: Prop[float]
    shrink: Prop[float]
    wrap: Prop[bool]
    position: Prop[Literal["relative", "absolute"]]
    top: Prop[Length]
    right: Prop[Length]
    bottom: Prop[Length]
    left: Prop[Length]
    overflow: Prop[Literal["visible", "hidden"]]
    src: Prop[str | os.PathLike[str] | bytes]
    fit: Prop[Literal["contain", "cover", "fill", "none"]]
    scroll: Prop[Literal["x", "y", "both"]]
    scroll_anchor: Prop[bool]
    stick_to_end: Prop[bool]
    reveal: Prop[tuple[float, float]]
    # Apariencia
    bg: Prop[Color]
    bg_hover: Prop[Color]
    bg_pressed: Prop[Color]
    gradient: Prop[tuple[Color, Color, float]]
    radius: Prop[float | str]
    border_width: Prop[float]
    border_color: Prop[Color]
    shadow: Prop[tuple[float, float, float, Color]]
    opacity: Prop[float]
    press_scale: Prop[float]
    transition: Prop[Any]
    animate_layout: Prop[Any]
    enter: Prop[Any]
    exit: Prop[Any]
    pulse: Prop[Any]
    scrollbar_color: Prop[Color]
    placeholder_color: Prop[Color]
    selection_color: Prop[Color]
    tooltip: Prop[str]
    cursor: Prop[Cursor]
    drop_target: Prop[bool]
    window_drag: Prop[WindowDrag]
    capture: Prop[bool]
    placement: Prop[str]
    offset: Prop[float]
    layer: Prop[Literal["base", "overlay"]]
    # Texto
    font_size: Prop[float]
    size: Prop[float]
    font_weight: Prop[float]
    weight: Prop[float]
    color: Prop[Color]
    font_family: Prop[str]
    family: Prop[str]
    line_height: Prop[float]
    letter_spacing: Prop[float]
    focus_color: Prop[Color]
    tooltip_bg: Prop[Color]
    tooltip_color: Prop[Color]
    max_lines: Prop[int]
    text_align: Prop[Literal["left", "center", "right"]]
    spans: Prop[Any]
    # Campos de texto
    multiline: Prop[bool]
    password: Prop[bool]
    placeholder: Prop[str]
    rows: Prop[int]
    # Foco
    focusable: Prop[bool]
    autofocus: Prop[bool]
    # Accesibilidad
    role: Prop[str]
    label: Prop[str]
    alt: Prop[str]
    description: Prop[str]
    value: Prop[str | float]
    checked: Prop[bool]
    selected: Prop[bool]
    expanded: Prop[bool]
    level: Prop[int]
    live: Prop[Literal["polite", "assertive", "off"]]
    position_in_set: Prop[int]
    set_size: Prop[int]
    sort: Prop[Literal["ascending", "descending"]]
    orientation: Prop[Literal["horizontal", "vertical"]]
    modal: Prop[bool]
    hidden: Prop[bool]
    value_min: Prop[float]
    value_max: Prop[float]
    value_step: Prop[float]
    # Manejadores
    on_click: Handler
    on_drag: Handler
    on_key: Handler
    on_focus: Handler
    on_blur: Handler
    on_scroll: Handler
    on_resize: Handler
    on_drop: Handler
    on_drop_hover: Handler
    on_context_menu: Callable[..., Any] | Sequence[Any] | None
    on_change: Handler
    on_submit: Handler
    on_link: Handler
    on_value: Handler


# Alias cómodos para los props de texto más usados.
ALIASES = {"size": "font_size", "weight": "font_weight", "family": "font_family"}

# Argumento → nombre con el que viaja al núcleo: el de estilo (con los alias
# resueltos) y el del evento (sin `on_`). Una consulta a estos dicts decide a la
# vez si el argumento existe y qué es.
STYLE_NAMES: dict[str, str] = {
    k: ALIASES.get(k, k) for k in Style.__optional_keys__ if not k.startswith("on_") and k != "key"
}
EVENT_NAMES: dict[str, str] = {k: k[3:] for k in Style.__optional_keys__ if k.startswith("on_")}

_ALL = sorted(STYLE_NAMES.keys() | EVENT_NAMES.keys())

# Props de color y `radius`: las que suelen llevar un `"$token"` como cadena.
# (Las anotaciones son texto o, según la versión de Python, un `ForwardRef` con él.)
TOKEN_PROPS = frozenset(
    STYLE_NAMES[k]
    for k, hint in Style.__annotations__.items()
    if getattr(hint, "__forward_arg__", hint) == "Prop[Color]" or k == "radius"
)

# Valores admitidos de las props enumeradas (los `Literal` de `Style`, por el
# nombre con el que viajan al núcleo; `tests/test_validation.py` comprueba que
# coinciden). `Element` mira aquí cada valor de texto: un valor mal escrito
# falla en la línea que creó el elemento y no al pintar.
ENUMS: dict[str, frozenset[str]] = {
    "direction": frozenset(("row", "column")),
    "align": frozenset(("start", "center", "end", "baseline", "stretch")),
    "justify": frozenset(("start", "center", "end", "between", "around", "evenly")),
    "position": frozenset(("relative", "absolute")),
    "overflow": frozenset(("visible", "hidden")),
    "fit": frozenset(("contain", "cover", "fill", "none")),
    "scroll": frozenset(("x", "y", "both")),
    "cursor": frozenset(
        (
            "default",
            "pointer",
            "text",
            "grab",
            "grabbing",
            "col-resize",
            "row-resize",
            "ns-resize",
            "ew-resize",
            "nesw-resize",
            "nwse-resize",
            "crosshair",
        )
    ),
    "window_drag": frozenset(("move", "n", "s", "e", "w", "ne", "nw", "se", "sw")),
    "layer": frozenset(("base", "overlay")),
    "text_align": frozenset(("left", "center", "right")),
    "live": frozenset(("polite", "assertive", "off")),
    "sort": frozenset(("ascending", "descending")),
    "orientation": frozenset(("horizontal", "vertical")),
    "placement": frozenset(
        side + end for side in ("top", "bottom", "left", "right") for end in ("", "-start", "-center", "-end")
    ),
}

# Lo que se suele escribir por costumbre de CSS u otros toolkits → el valor de Aurora.
VALUE_ALIASES: dict[str, dict[str, str]] = {
    "justify": {
        "space-between": "between",
        "space_between": "between",
        "space-around": "around",
        "space_around": "around",
        "space-evenly": "evenly",
        "space_evenly": "evenly",
        "flex-start": "start",
        "flex-end": "end",
        "left": "start",
        "right": "end",
        "top": "start",
        "bottom": "end",
        "middle": "center",
    },
    "align": {
        "flex-start": "start",
        "flex-end": "end",
        "left": "start",
        "right": "end",
        "top": "start",
        "bottom": "end",
        "middle": "center",
        "stretched": "stretch",
        "fill": "stretch",
    },
    "text_align": {"start": "left", "end": "right", "middle": "center"},
    "direction": {
        "horizontal": "row",
        "vertical": "column",
        "col": "column",
        "columns": "column",
        "rows": "row",
    },
    "overflow": {"clip": "hidden"},
    "position": {"fixed": "absolute", "static": "relative"},
    "cursor": {"hand": "pointer", "move": "grab", "ibeam": "text", "arrow": "default"},
    "fit": {"contains": "contain", "stretch": "fill"},
    "orientation": {"row": "horizontal", "column": "vertical"},
    "placement": {
        "above": "top",
        "below": "bottom",
        "top-left": "top-start",
        "top-right": "top-end",
        "bottom-left": "bottom-start",
        "bottom-right": "bottom-end",
    },
}


def suggest(name: str, valid: Iterable[str], aliases: dict[str, str] | None = None) -> str | None:
    """El valor de `valid` que se quiso escribir: un alias conocido o, si no, el
    más parecido (solo si se parece bastante; uno lejano confunde más que ayuda)."""
    import difflib  # solo al fallar: no cuesta en el arranque

    if aliases and name in aliases:
        return aliases[name]
    lowered = name.lower().strip()
    if lowered in valid:
        return lowered
    close = difflib.get_close_matches(lowered, list(valid), n=1, cutoff=0.7)
    return close[0] if close else None


def choices(valid: Iterable[str]) -> str:
    """Los valores válidos como texto: `'a', 'b' o 'c'`."""
    items = [repr(v) for v in sorted(valid)]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " o " + items[-1]


def invalid_choice(
    what: str, value: Any, valid: Iterable[str], aliases: dict[str, str] | None = None
) -> ValueError:
    """El error de un valor que no está entre los válidos, con la sugerencia y la lista."""
    valid = list(valid)
    message = f"{what} no acepta {value!r}."
    close = suggest(value, valid, aliases) if isinstance(value, str) else None
    if close is not None:
        message += f" ¿Quisiste decir {close!r}?"
    return ValueError(f"{message} Valores válidos: {choices(valid)}.")


def invalid_value(kind: str, prop: str, value: Any) -> ValueError:
    """El error de una prop enumerada con un valor que no existe."""
    name = ALIASES.get(prop, prop)
    return invalid_choice(f"{_called_as(kind)}({prop}=...)", value, ENUMS[name], VALUE_ALIASES.get(name))


def _called_as(kind: str) -> str:
    """La función de Aurora que llamó quien escribió el argumento (`column`,
    `button`…): la última de la pila antes de salir del paquete."""
    name = None
    frame = sys._getframe(2)
    while frame is not None:
        module = frame.f_globals.get("__name__", "")
        if module != "aurora" and not module.startswith("aurora."):
            break
        name = frame.f_code.co_name
        frame = frame.f_back
    return name if name and not name.startswith("_") and name != "<module>" else kind


# Nombres de otras librerías (CSS, Flutter, SwiftUI…) → la prop de Aurora. Un
# parecido de letras no los encuentra (`secure` se parece más a `capture`).
PROP_ALIASES = {
    "background": "bg",
    "background_color": "bg",
    "bgcolor": "bg",
    "border_radius": "radius",
    "corner_radius": "radius",
    "rounded": "radius",
    "flex": "grow",
    "flex_grow": "grow",
    "flex_shrink": "shrink",
    "flex_direction": "direction",
    "flex_wrap": "wrap",
    "align_items": "align",
    "justify_content": "justify",
    "font_color": "color",
    "text_color": "color",
    "foreground": "color",
    "fg": "color",
    "font": "font_family",
    "bold": "weight",
    "z_index": "layer",
    "hint": "placeholder",
    "secure": "password",
    "secret": "password",
    "masked": "password",
    "obscure": "password",
    "obscure_text": "password",
    "is_password": "password",
    "aria_label": "label",
    "title": "tooltip",
    "on_press": "on_click",
    "on_tap": "on_click",
    "on_input": "on_change",
    "on_enter": "on_submit",
}

# Lo que no existe con ningún nombre, y qué usar en su lugar.
_MISSING = {
    "margin": "No hay `margin`: separa con `gap` o `padding` en el contenedor.",
    "on_hover": "No hay `on_hover`: `bg_hover` cambia el fondo y `tooltip` muestra una ayuda.",
}


def unknown_prop(kind: str, name: str) -> TypeError:
    """El error de un argumento que no es ni estilo ni manejador, con la sugerencia."""
    import difflib  # solo al fallar: no cuesta en el arranque

    what = "el manejador" if name.startswith("on_") else "la prop"
    message = f"{_called_as(kind)}() no acepta {what} {name!r}."
    snake = "".join(f"_{c.lower()}" if c.isupper() else c for c in name).lstrip("_")
    base = snake.removeprefix("margin_").removesuffix("_margin")
    if base in _MISSING or snake.startswith("margin"):
        return TypeError(f"{message} {_MISSING.get(base, _MISSING['margin'])}")
    alias = PROP_ALIASES.get(snake)
    # Solo una sugerencia que se parezca bastante: una lejana confunde más que ayuda.
    close = [alias] if alias else difflib.get_close_matches(snake, _ALL, n=1, cutoff=0.75)
    if close:
        return TypeError(f"{message} ¿Quisiste decir {close[0]!r}?")
    return TypeError(f"{message} Las propiedades válidas están en la referencia (Propiedades de estilo).")
