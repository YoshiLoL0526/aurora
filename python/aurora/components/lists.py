"""Lista virtualizada: solo construye las filas visibles."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..elements import Element, box, column, scroll
from ..signal import Signal
from ._state import _VIEWPORTS

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
