"""Variantes de `Style` sin los parámetros propios de cada componente.

Generado por `tests/test_validation.py` a partir de `aurora._style.Style`: no
lo edites a mano. Para regenerarlo:

    AURORA_UPDATE_API=1 uv run pytest tests/test_validation.py
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from typing import Any, Literal, TypedDict

from ._style import Align, Color, Cursor, Edges, Handler, Justify, Length, Prop, WindowDrag


class AccordionStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `accordion()`."""

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


class AvatarStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `avatar()`."""

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


class ButtonStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `button()`."""

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


class ChartStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `chart()`."""

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


class CheckboxStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `checkbox()`."""

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
    alt: Prop[str]
    description: Prop[str]
    value: Prop[str | float]
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
    on_submit: Handler
    on_link: Handler
    on_value: Handler


class ColorPickerStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `color_picker()`."""

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
    on_submit: Handler
    on_link: Handler
    on_value: Handler


class ComboboxStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `combobox()`."""

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
    rows: Prop[int]
    # Foco
    focusable: Prop[bool]
    autofocus: Prop[bool]
    # Accesibilidad
    role: Prop[str]
    label: Prop[str]
    alt: Prop[str]
    description: Prop[str]
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
    on_submit: Handler
    on_link: Handler
    on_value: Handler


class DatePickerStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `date_picker()`."""

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
    rows: Prop[int]
    # Foco
    focusable: Prop[bool]
    autofocus: Prop[bool]
    # Accesibilidad
    role: Prop[str]
    label: Prop[str]
    alt: Prop[str]
    description: Prop[str]
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
    on_submit: Handler
    on_link: Handler
    on_value: Handler


class DialogStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `dialog()`."""

    # Layout
    direction: Prop[Literal["row", "column"]]
    gap: Prop[float]
    padding: Prop[Edges]
    align: Prop[Align]
    justify: Prop[Justify]
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


class DividerStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `divider()`."""

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


class FieldStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `field()`."""

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


class ImageStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `image()`."""

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


class MarkdownStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `markdown()`."""

    # Layout
    direction: Prop[Literal["row", "column"]]
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
    on_value: Handler


class MenuStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `menu()`."""

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


class NumberInputStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `number_input()`."""

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
    on_submit: Handler
    on_link: Handler
    on_value: Handler


class PagesStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `pages()`."""

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


class PopoverStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `popover()`."""

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


class ProgressStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `progress()`."""

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


class RadioStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `radio()`."""

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


class RichTextStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `rich_text()`."""

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


class SegmentedStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `segmented()`."""

    # Layout
    direction: Prop[Literal["row", "column"]]
    gap: Prop[float]
    padding: Prop[Edges]
    align: Prop[Align]
    justify: Prop[Justify]
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


class SelectStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `select()`."""

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
    rows: Prop[int]
    # Foco
    focusable: Prop[bool]
    autofocus: Prop[bool]
    # Accesibilidad
    role: Prop[str]
    label: Prop[str]
    alt: Prop[str]
    description: Prop[str]
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


class SkeletonStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `skeleton()`."""

    key: str | None
    # Layout
    direction: Prop[Literal["row", "column"]]
    padding: Prop[Edges]
    align: Prop[Align]
    justify: Prop[Justify]
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


class SliderStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `slider()`."""

    # Layout
    direction: Prop[Literal["row", "column"]]
    gap: Prop[float]
    padding: Prop[Edges]
    align: Prop[Align]
    justify: Prop[Justify]
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
    on_submit: Handler
    on_link: Handler
    on_value: Handler


class SortableStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `sortable()`."""

    # Layout
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


class SpinnerStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `spinner()`."""

    # Layout
    direction: Prop[Literal["row", "column"]]
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


class SplitterStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `splitter()`."""

    # Layout
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
    on_submit: Handler
    on_link: Handler
    on_value: Handler


class SwitchStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `switch()`."""

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
    on_submit: Handler
    on_link: Handler
    on_value: Handler


class TableStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `table()`."""

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


class TabsStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `tabs()`."""

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


class TextInputStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `text_input()`."""

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
    rows: Prop[int]
    # Foco
    focusable: Prop[bool]
    autofocus: Prop[bool]
    # Accesibilidad
    role: Prop[str]
    label: Prop[str]
    alt: Prop[str]
    description: Prop[str]
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
    on_link: Handler
    on_value: Handler


class TextareaStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `textarea()`."""

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
    # Foco
    focusable: Prop[bool]
    autofocus: Prop[bool]
    # Accesibilidad
    role: Prop[str]
    label: Prop[str]
    alt: Prop[str]
    description: Prop[str]
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
    on_link: Handler
    on_value: Handler


class TimePickerStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `time_picker()`."""

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
    rows: Prop[int]
    # Foco
    focusable: Prop[bool]
    autofocus: Prop[bool]
    # Accesibilidad
    role: Prop[str]
    label: Prop[str]
    alt: Prop[str]
    description: Prop[str]
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
    on_submit: Handler
    on_link: Handler
    on_value: Handler


class TitleBarStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `title_bar()`."""

    # Layout
    direction: Prop[Literal["row", "column"]]
    gap: Prop[float]
    padding: Prop[Edges]
    align: Prop[Align]
    justify: Prop[Justify]
    width: Prop[Length]
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


class ToastStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `toast()`."""

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


class TreeStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `tree()`."""

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
    alt: Prop[str]
    description: Prop[str]
    value: Prop[str | float]
    checked: Prop[bool]
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


class VirtualListStyle(TypedDict, total=False):
    """`Style` sin las claves que son parámetros de `virtual_list()`."""

    # Layout
    direction: Prop[Literal["row", "column"]]
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
