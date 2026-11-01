"""Barra de título propia para ventanas sin marco (`App(..., decorations=False)`)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Literal

from ..elements import Child, Element, TextLike, box, row, spacer, text

if TYPE_CHECKING:
    from typing import Unpack

    from .._style_variants import TitleBarStyle

if TYPE_CHECKING:
    from .. import Window

# Rojo de cerrar de Windows: el botón lo toma al pasar por encima, en claro y en oscuro.
_CLOSE_HOVER = "#C42B1C"
# Los «semáforos» de macOS: cerrar, minimizar y maximizar.
_LIGHTS = ("#FF5F57", "#FEBC2E", "#28C840")


def _glyph(kind: str, bg: Any) -> Element:
    """El dibujo de un botón de ventana, hecho con cajas (toma el color del tema)."""
    if kind == "minimize":
        return box(width=10, height=1, bg="$text")
    if kind == "maximize":
        return box(width=10, height=10, radius=1, border_width=1, border_color="$text")
    if kind == "restore":
        square: dict[str, Any] = dict(
            position="absolute", width=8, height=8, radius=1, border_width=1, border_color="$text"
        )
        return box(width=10, height=10)[
            box(top=0, right=0, **square),
            box(bottom=0, left=0, bg=bg, **square),
        ]
    return text("✕", size=12, line_height=1)


def title_bar(
    title: TextLike | None = None,
    *,
    icon: Element | None = None,
    actions: Child = None,
    window: Window | None = None,
    controls: bool | Literal["windows", "macos"] = True,
    height: float = 36,
    key: str = "title-bar",
    **style: Unpack[TitleBarStyle],
) -> Element:
    """Barra de título para una ventana sin marco: se arrastra y lleva los botones de la ventana.

    Toda la barra mueve la ventana (`window_drag="move"`) y un doble clic la
    maximiza o la restaura; los botones y controles que pongas en ella siguen
    recibiendo sus clics. `icon` va delante de `title` y `actions` (un elemento
    o una lista), justo antes de los botones de minimizar, maximizar o
    restaurar, y cerrar (`controls=False` los quita). Cerrar pasa por el
    `on_close` de la ventana, como el botón del sistema.

    Actúa sobre la ventana cuya vista se construye (`current_window()`) o
    sobre `window`. Los botones siguen al sistema: en macOS, los tres círculos
    a la izquierda; en Windows y Linux, a la derecha. `controls="macos"` o
    `controls="windows"` fija uno de los dos estilos en todos.
    """
    from .. import current_window

    target = window if window is not None else current_window()
    bg = style.get("bg", "$surface")
    mac = controls == "macos" or (controls is True and sys.platform == "darwin")

    def toggle() -> None:
        target.maximized = not target.maximized

    def windows_button(kind: str, label: str, on_click: Any) -> Element:
        return box(
            key=f"{key}-{kind}",
            width=46,
            align="center",
            justify="center",
            bg_hover=_CLOSE_HOVER if kind == "close" else "$surface_hover",
            bg_pressed=_CLOSE_HOVER if kind == "close" else "$surface_pressed",
            on_click=on_click,
            # Como los del sistema, no entran en el orden de Tab (un lector los pulsa igual).
            focusable=False,
            role="button",
            label=label,
        )[_glyph(kind, bg)]

    def light(kind: str, label: str, color: str, on_click: Any) -> Element:
        return box(
            key=f"{key}-{kind}",
            width=12,
            height=12,
            radius="$full",
            bg=color,
            on_click=on_click,
            focusable=False,
            role="button",
            label=label,
        )

    maximized = target.maximized if controls else False
    if not controls:
        buttons: Element | None = None
    elif mac:
        buttons = row(gap=8, align="center", padding=(0, 4, 0, 0))[
            light("close", "Cerrar", _LIGHTS[0], target.request_close),
            light("minimize", "Minimizar", _LIGHTS[1], target.minimize),
            light("maximize", "Restaurar" if maximized else "Maximizar", _LIGHTS[2], toggle),
        ]
    else:
        buttons = row(align="stretch")[
            windows_button("minimize", "Minimizar", target.minimize),
            windows_button(
                "restore" if maximized else "maximize", "Restaurar" if maximized else "Maximizar", toggle
            ),
            windows_button("close", "Cerrar", target.request_close),
        ]
    props: dict[str, Any] = {"bg": bg, **style}
    return row(
        key=key,
        window_drag="move",
        height=height,
        shrink=0,
        align="stretch" if not mac else "center",
        **props,
    )[
        mac and buttons and row(align="center", padding=(0, 0, 0, 12))[buttons],
        row(gap=8, align="center", padding=(0, 12))[
            icon,
            title is not None and text(title, size=12, weight=500, color="$muted", max_lines=1),
        ],
        spacer(),
        actions is not None and row(gap=4, align="center", padding=(0, 8))[actions],
        not mac and buttons,
    ]
