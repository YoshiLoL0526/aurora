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
from collections.abc import Callable, Sequence
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
    live: Prop[Literal["polite", "assertive"]]
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


def unknown_prop(kind: str, name: str) -> TypeError:
    """El error de un argumento que no es ni estilo ni manejador, con la sugerencia."""
    import difflib  # solo al fallar: no cuesta en el arranque

    what = "el manejador" if name.startswith("on_") else "la prop"
    message = f"{_called_as(kind)}() no acepta {what} {name!r}."
    close = difflib.get_close_matches(name, _ALL, n=1)
    if close:
        return TypeError(f"{message} ¿Quisiste decir {close[0]!r}?")
    return TypeError(f"{message} Las propiedades válidas están en la referencia (Propiedades de estilo).")
