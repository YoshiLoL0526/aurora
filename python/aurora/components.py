"""Componentes con estilo por defecto, construidos solo con primitivas.

Casi ningún componente necesita código nativo: el núcleo Rust sabe pintar
cajas, texto, sombras y gradientes, animar estados hover/pressed y editar texto
(el nodo `input`). Todo lo demás se compone aquí, en Python.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from .elements import Element, TextLike, box, column, row, text
from .signal import Signal

Variant = Literal["primary", "soft", "ghost"]

_BUTTON_VARIANTS: dict[str, dict[str, Any]] = {
    "primary": dict(
        bg="$primary",
        bg_hover="$primary_hover",
        bg_pressed="$primary_pressed",
        color="#FFFFFF",
        shadow=(0, 6, 18, "$glow"),
    ),
    "soft": dict(
        bg="$surface_hover",
        bg_hover="$surface_pressed",
        bg_pressed="$border",
        color="$text",
        border_width=1,
        border_color="$border",
    ),
    "ghost": dict(
        bg="#00000000",
        bg_hover="$surface_hover",
        bg_pressed="$surface_pressed",
        color="$muted",
    ),
}


def button(
    label: TextLike,
    on_click: Callable[[], Any] | None = None,
    *,
    variant: Variant = "primary",
    key: str | None = None,
    **style: Any,
) -> Element:
    styles = {
        **_BUTTON_VARIANTS[variant],
        "padding": (10, 18),
        "radius": "$md",
        "align": "center",
        "justify": "center",
        "press_scale": 0.96,
        "font_weight": 600,
        **style,
    }
    return box(on_click=on_click, key=key, **styles)[text(label)]


def card(**style: Any) -> Element:
    return column(
        **{
            "bg": "$surface",
            "radius": "$lg",
            "padding": 20,
            "gap": 12,
            "border_width": 1,
            "border_color": "$border",
            "shadow": (0, 10, 30, "$shadow"),
            **style,
        }
    )


def badge(label: TextLike, *, tone: str = "accent") -> Element:
    return row(padding=(4, 10), radius="$full", bg=f"${tone}", align="center")[
        text(label, size=11, weight=700, color="#0B0D14", letter_spacing=0.4)
    ]


def stat(label: str, value: TextLike, delta: str | None = None, *, positive: bool = True) -> Element:
    """Tarjeta de métrica para dashboards."""
    return card(grow=1, gap=6)[
        text(label, size=12, weight=500, color="$muted", letter_spacing=0.3),
        row(gap=10, align="baseline")[
            text(value, size=28, weight=700),
            delta and text(delta, size=13, weight=600, color="$success" if positive else "$danger"),
        ],
    ]


_INPUT_STYLE: dict[str, Any] = dict(
    bg="$surface",
    border_width=1,
    border_color="$border",
    radius="$md",
    padding=(9, 12),
)


def _field(
    value: Signal[str] | TextLike,
    on_change: Callable[[str], Any] | None,
    on_submit: Callable[[str], Any] | None,
    key: str | None,
    style: dict[str, Any],
) -> Element:
    if isinstance(value, Signal):
        signal = value

        def change(text: str) -> None:
            signal.set(text)
            if on_change is not None:
                on_change(text)

        handler: Callable[[str], Any] | None = change
    else:
        handler = on_change
    return Element(
        "input",
        content=value,
        key=key,
        on_change=handler,
        on_submit=on_submit,
        **{**_INPUT_STYLE, **style},
    )


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
