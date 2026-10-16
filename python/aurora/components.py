"""Componentes con estilo por defecto, construidos solo con primitivas.

Casi ningún componente necesita código nativo: el núcleo Rust sabe pintar
cajas, texto, sombras y gradientes, animar estados hover/pressed y editar texto
(el nodo `input`). Todo lo demás se compone aquí, en Python.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Hashable, Sequence
from typing import Any, Literal, TypeVar

from .elements import Element, TextLike, box, column, image, row, scroll, spacer, text
from .signal import Signal

T = TypeVar("T", bound=Hashable)
Options = Sequence[T] | Sequence[tuple[T, str]]

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


# --- Utilidades -------------------------------------------------------------

# Iconos vectoriales: nítidos a cualquier tamaño y densidad de pantalla.
_CHECK = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none" stroke="#FFFFFF" '
    b'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 8.5l3 3 6-7"/></svg>'
)
_CHEVRON = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none" stroke="#8A91A8" '
    b'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6l4 4 4-4"/></svg>'
)


def _toggle(
    state: Signal[bool] | bool, on_change: Callable[[bool], Any] | None
) -> tuple[bool, Callable[[], None]]:
    """Valor actual y acción de alternarlo, para controles enlazados a un `Signal[bool]`."""
    current = state() if isinstance(state, Signal) else bool(state)

    def flip() -> None:
        value = not current
        if isinstance(state, Signal):
            state.set(value)
        if on_change is not None:
            on_change(value)

    return current, flip


def _items(options: Options) -> list[tuple[Any, str]]:
    return [o if isinstance(o, tuple) else (o, str(o)) for o in options]


# --- Componentes ------------------------------------------------------------


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


def tooltip(child: Element, tip: str) -> Element:
    """Muestra `tip` al dejar el puntero medio segundo sobre `child`.

    Equivale a pasar `tooltip="..."` a cualquier elemento.
    """
    child.style["tooltip"] = tip
    return child


def checkbox(
    checked: Signal[bool] | bool,
    label: TextLike | None = None,
    *,
    on_change: Callable[[bool], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Casilla de verificación. Con un `Signal[bool]` se enlaza sola; `on_change(valor)`
    se llama en cada cambio. Se activa con clic, Enter o Espacio."""
    on, flip = _toggle(checked, on_change)
    mark = box(
        width=18,
        height=18,
        radius=5,
        align="center",
        justify="center",
        shrink=0,
        bg="$primary" if on else "$surface",
        border_width=0 if on else 1.5,
        border_color="$muted",
    )[on and image(_CHECK, width=12)]
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
    """Interruptor encendido/apagado. Igual que `checkbox`, con otra forma."""
    value, flip = _toggle(on, on_change)
    track = box(width=36, height=20, radius="$full", shrink=0, bg="$primary" if value else "$border")[
        box(
            position="absolute",
            top=2,
            left=18 if value else 2,
            width=16,
            height=16,
            radius="$full",
            bg="#FFFFFF",
            shadow=(0, 1, 3, "#00000040"),
        )
    ]
    return row(**{"gap": 10, "align": "center", "radius": 10, "key": key, "on_click": flip, **style})[
        track, label is not None and text(label)
    ]


def tabs(options: Options, selected: Signal[Any], *, key: str | None = None, **style: Any) -> Element:
    """Pestañas. `options` son valores (o pares `(valor, etiqueta)`) y `selected` el
    `Signal` con el valor activo. Con una pestaña enfocada, ← y → cambian de pestaña."""
    items = _items(options)
    values = [v for v, _ in items]
    base = key or f"tabs-{id(selected)}"

    def on_key(e: Any) -> bool | None:
        if e.key in ("ArrowLeft", "ArrowRight") and selected() in values:
            step = 1 if e.key == "ArrowRight" else -1
            selected.set(values[(values.index(selected()) + step) % len(values)])
            return True
        return None

    def tab(value: Any, label: str) -> Element:
        active = selected() == value
        return column(
            key=f"{base}-{value}",
            gap=8,
            padding=(8, 12, 0, 12),
            radius=6,
            on_click=lambda: selected.set(value),
        )[
            text(label, weight=600, color="$text" if active else "$muted"),
            box(height=2, radius=1, bg="$primary" if active else "#00000000"),
        ]

    return column(**{"gap": 0, **style})[
        row(gap=4, on_key=on_key)[[tab(v, label) for v, label in items]],
        divider(),
    ]


# Estado abierto/cerrado de cada `select`, por key (los componentes no tienen estado propio).
_OPEN: dict[str, Signal[bool]] = {}
_SELECT_HEIGHT = 40


def select(
    value: Signal[Any],
    options: Options,
    *,
    placeholder: str = "Elegir…",
    key: str | None = None,
    **style: Any,
) -> Element:
    """Desplegable para elegir un valor de `options` (valores o pares `(valor, etiqueta)`).

    La lista se abre por encima del resto (`layer="overlay"`) y se cierra al elegir, al
    hacer clic fuera o con Esc. Con el desplegable enfocado, ↑ y ↓ cambian el valor.
    """
    items = _items(options)
    values = [v for v, _ in items]
    k = key or f"select-{id(value)}"
    open_ = _OPEN.setdefault(k, Signal(False))
    current = next((label for v, label in items if v == value()), None)

    def choose(v: Any) -> None:
        value.set(v)
        open_.set(False)

    def on_key(e: Any) -> bool | None:
        if e.key in ("Escape", "Enter") and open_():
            open_.set(False)
            return True
        if e.key in ("ArrowDown", "ArrowUp") and values:
            i = values.index(value()) if value() in values else -1
            step = 1 if e.key == "ArrowDown" else -1
            value.set(values[max(0, min(len(values) - 1, i + step))])
            return True
        return None

    trigger = row(
        key=k,
        height=_SELECT_HEIGHT,
        gap=8,
        align="center",
        padding=(0, 12),
        radius="$md",
        bg="$surface",
        bg_hover="$surface_hover",
        border_width=1,
        border_color="$border",
        on_click=lambda: open_.set(not open_()),
        on_key=on_key,
    )[
        current is not None and text(current, max_lines=1),
        current is None and text(placeholder, color="$muted", max_lines=1),
        spacer(),
        image(_CHEVRON, width=14),
    ]

    def option(i: int, v: Any, label: str) -> Element:
        chosen = v == value()
        return row(
            key=f"{k}-opt-{i}",
            padding=(8, 10),
            radius=8,
            bg="$surface_hover" if chosen else "#00000000",
            bg_hover="$surface_hover",
            on_click=lambda: choose(v),
        )[text(label, weight=600 if chosen else 400, max_lines=1)]

    menu = open_() and [
        # Fondo invisible que cierra al hacer clic fuera.
        box(
            layer="overlay",
            position="absolute",
            left=-10_000,
            top=-10_000,
            width=20_000,
            height=20_000,
            focusable=False,
            on_click=lambda: open_.set(False),
        ),
        box(
            layer="overlay",
            position="absolute",
            top=_SELECT_HEIGHT + 6,
            left=0,
            right=0,
            padding=4,
            radius="$md",
            bg="$surface",
            border_width=1,
            border_color="$border",
            shadow=(0, 12, 32, "$shadow"),
        )[scroll(max_height=240, gap=2)[[option(i, v, label) for i, (v, label) in enumerate(items)]]],
    ]
    return column(**{"min_width": 160, **style})[trigger, menu]


# Zona visible de cada `virtual_list` (desplazamiento y alto), por key.
_VIEWPORTS: dict[str, Signal[tuple[float, float] | None]] = {}
# Alto que se supone visible hasta el primer frame, cuando el núcleo lo mide.
_GUESSED_HEIGHT = 1080.0


def virtual_list(
    count: int,
    item: Callable[[int], Element],
    *,
    item_height: float,
    key: str,
    gap: float = 0,
    overscan: int = 4,
    **style: Any,
) -> Element:
    """Lista desplazable de `count` filas que solo construye las visibles.

    `item(i)` devuelve la fila `i`. Todas las filas miden `item_height` (más `gap`
    entre ellas), así que la lista sabe su alto total y qué filas caen en la zona
    visible sin construirlas: con 100 000 filas, cada reconstrucción crea unas pocas
    decenas. Se reconstruye al desplazarse solo cuando cambia el rango visible;
    `overscan` filas de más por cada lado cubren el desplazamiento entre medias.

    Cada fila ocupa un hueco de todo el ancho y `item_height` de alto: dale `grow=1`
    a su raíz para que lo rellene. `key` es obligatoria: guarda la posición y la zona
    visible. Con `@component`, las filas que siguen visibles no se reconstruyen.
    """
    if item_height <= 0:
        raise ValueError("item_height debe ser positivo")
    viewport = _VIEWPORTS.setdefault(key, Signal(None))
    stride = item_height + gap

    def visible(y: float, height: float) -> tuple[int, int]:
        first = max(0, int(y // stride) - overscan)
        last = min(count, int((y + height) // stride) + 1 + overscan)
        return first, max(first, last)

    def on_scroll(e: Any) -> None:
        current = viewport()
        if current is None or visible(*current) != visible(e.y, e.height):
            viewport.set((e.y, e.height))

    first, last = visible(*(viewport() or (0.0, _GUESSED_HEIGHT)))
    total = count * item_height + max(0, count - 1) * gap
    rows = [
        column(key=f"{key}#{i}", position="absolute", top=i * stride, left=0, right=0, height=item_height)[
            item(i)
        ]
        for i in range(first, last)
    ]
    return scroll(key=key, on_scroll=on_scroll, **style)[box(height=total, shrink=0)[rows]]
