"""Componentes con estilo por defecto, construidos solo con primitivas.

Ningún componente necesita código nativo: el núcleo Rust sabe pintar cajas,
texto, sombras y gradientes, y animar estados hover/pressed. Todo lo demás
se compone aquí, en Python.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from .elements import Element, TextLike, box, column, row, text

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
