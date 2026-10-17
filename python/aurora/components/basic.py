"""Componentes básicos: botón, tarjeta, insignia, métrica, separador y avatar."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, Literal

from ..elements import Element, TextLike, box, column, image, row, text

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


def divider(*, vertical: bool = False, color: str = "$border", **style: Any) -> Element:
    """Línea separadora de 1 px. Horizontal por defecto; `vertical=True` en una `row`."""
    size = {"width": 1} if vertical else {"height": 1}
    return box(**{**size, "bg": color, "shrink": 0, **style})


_AVATAR_TONES = ("$primary", "$accent", "$success", "$muted")


def avatar(
    name: str = "",
    *,
    src: str | os.PathLike[str] | bytes | None = None,
    size: float = 32,
    **style: Any,
) -> Element:
    """Avatar circular: la imagen `src` recortada, o las iniciales de `name` sobre un
    color estable (el mismo nombre siempre da el mismo color)."""
    shape = {"width": size, "height": size, "radius": "$full", "shrink": 0}
    if src is not None:
        return image(src, fit="cover", **{**shape, **style})
    initials = "".join(word[0] for word in name.split()[:2]).upper() or "?"
    tone = _AVATAR_TONES[sum(map(ord, name)) % len(_AVATAR_TONES)]
    return box(**{**shape, "bg": tone, "align": "center", "justify": "center", **style})[
        text(initials, size=size * 0.38, weight=700, color="#FFFFFF")
    ]
