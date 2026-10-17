"""Navegación: pestañas, páginas, selector segmentado y acordeón."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .. import _motion as motion
from .. import animate
from ..elements import Element, box, column, row, scroll, spacer, text
from ..signal import Signal
from ._shared import Options, _items
from .basic import divider


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
            text(label, weight=600, color="$text" if active else "$muted", transition=motion.fast()),
            box(height=2, radius=1, bg="$primary" if active else "#00000000", transition=motion.fast()),
        ]

    return column(**{"gap": 0, **style})[
        row(gap=4, on_key=on_key)[[tab(v, label) for v, label in items]],
        divider(),
    ]


def pages(
    current: Signal[Any],
    views: Mapping[Any, Callable[[], Element]],
    *,
    key: str = "pages",
    **style: Any,
) -> Element:
    """Una vista por valor de `current`, con transición al cambiar.

    `views` asocia cada valor con una función que devuelve el contenido. Es el
    compañero natural de `tabs` (comparten `Signal`) para cambiar de página: al
    cambiar el valor, la vista nueva entra fundiéndose y la anterior se va.
    Un valor sin vista lanza `ValueError` con las opciones disponibles.

    Cada página es su propio `scroll` — con la key `f"{key}-{valor}"` — que
    ocupa el espacio libre, así que no hacen falta `height`; los `estilo` van a
    él (`padding`, `gap`…). Al volver a una página, empieza arriba: el núcleo
    guarda la posición mientras existe, no entre visitas.
    """
    value = current()
    view = views.get(value)
    if view is None:
        options = ", ".join(repr(v) for v in views)
        raise ValueError(f"pages: no hay vista para {value!r} (usa {options})")
    return scroll(
        key=f"{key}-{value}",
        enter=motion.entering(animate.fade()),
        exit=motion.leaving(animate.fade()),
        **style,
    )[view()]


def segmented(
    options: Options, selected: Signal[Any], *, width: float = 220, key: str | None = None, **style: Any
) -> Element:
    """Selector segmentado: un pulgar se desliza hasta la opción activa.

    `options` son valores (o pares `(valor, etiqueta)`) y `selected`, el `Signal`
    con el valor activo. Las ranuras miden todas lo mismo (de ahí el `width`, en
    píxeles: es lo que permite que el pulgar se ancle por fracción). Cada opción
    tiene la key `f"{key}-{valor}"` y el pulgar la suya, `f"{key}-thumb"`. Los
    `estilo` van al contenedor.
    """
    items = _items(options)
    values = [v for v, _ in items]
    base = key or f"segmented-{id(selected)}"
    n = max(1, len(items))
    index = values.index(selected()) if selected() in values else 0

    def option(value: Any, label: str) -> Element:
        on = selected() == value
        return box(
            key=f"{base}-{value}",
            grow=1,
            width=0,
            padding=(6, 12),
            radius=9,
            align="center",
            justify="center",
            bg_hover=None if on else "$surface_pressed",
            on_click=lambda v=value: selected.set(v),
        )[
            text(
                label,
                size=12,
                weight=600,
                color="$text" if on else "$muted",
                max_lines=1,
                transition=motion.fast(),
            )
        ]

    return row(**{"padding": 3, "radius": "$md", "bg": "$surface_hover", "width": width, **style})[
        box(grow=1, width=0)[
            # El pulgar, primero: se pinta debajo de las etiquetas.
            box(
                key=f"{base}-thumb",
                position="absolute",
                left=f"{index * 100 / n:.4f}%",
                top=0,
                bottom=0,
                width=f"{100 / n:.4f}%",
                radius=9,
                bg="$surface",
                shadow=(0, 1, 4, "$shadow"),
                animate_layout=motion.move(),
            ),
            row()[[option(v, label) for v, label in items]],
        ],
    ]


def accordion(
    sections: Sequence[tuple[Any, str, Element]],
    open: Signal[Any],
    *,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Acordeón: cada sección se despliega al pulsar su cabecera.

    `sections` son triples `(valor, título, contenido)` y `open` el `Signal` con
    la sección desplegada (`None` con todas plegadas; pulsar la cabecera de la
    abierta la pliega). El contenido se despliega con la altura animada y
    `overflow="hidden"`, se queda montado al plegarse (conserva su estado) y no
    recibe clics mientras está oculto. Cada sección tiene la key
    `f"{key}-{valor}"`.
    """
    base = key or f"accordion-{id(open)}"

    def section(value: Any, title: str, content: Element) -> Element:
        shown = open() == value
        # El contenido no se encoge al plegarse: se recorta, no se aplasta.
        content.style.setdefault("shrink", 0)
        return column(key=f"{base}-{value}", gap=0)[
            row(
                padding=(10, 12),
                radius="$md",
                align="center",
                bg_hover="$surface_hover",
                on_click=lambda v=value, on=shown: open.set(None if on else v),
            )[
                text(title, size=14, weight=600),
                spacer(),
                text("▾" if shown else "▸", size=12, color="$muted"),
            ],
            box(
                overflow="hidden",
                animate_layout=motion.move(),
                height=None if shown else 0,
            )[content],
        ]

    return column(**{"gap": 4, **style})[[section(v, t, c) for v, t, c in sections]]
