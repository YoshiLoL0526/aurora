"""Distribución del espacio: `splitter` (dos paneles con un separador arrastrable)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from ..elements import Element, box
from ..signal import Signal
from ._state import _DRAG_START, _EXTENTS, _SPLITS

# Grosor de la franja del separador (la línea visible mide 1 px).
_HANDLE = 7


def splitter(
    first: Element,
    second: Element,
    *,
    size: Signal[float] | float = 240,
    direction: Literal["row", "column"] = "row",
    min_sizes: tuple[float, float] = (80, 80),
    step: float = 16,
    on_change: Callable[[float], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Dos paneles con un separador entre ellos que se arrastra para repartir el espacio.

    Con `direction="row"` los paneles van uno al lado del otro (el separador es
    vertical y cambia anchos); con `"column"`, uno encima del otro. `size` es el
    tamaño del primer panel en píxeles: con un `Signal[float]` queda enlazado
    (arrastrar lo cambia y asignarlo mueve el separador); con un número es el
    tamaño inicial y el estado vive en la `key`, que entonces es obligatoria. El
    segundo panel ocupa el resto.

    `min_sizes` son los mínimos de cada panel: el separador no los rebasa, y si
    la ventana encoge, el primer panel cede hasta su mínimo (sin cambiar `size`,
    así que recupera su tamaño al volver a crecer). El contenedor se mide tras
    el primer layout (con `on_resize`): hasta entonces no hay máximo. Con el separador enfocado,
    las flechas lo mueven `step` píxeles e Inicio/Fin lo llevan a los extremos.
    `on_change(tamaño)` se llama en cada cambio.

    Cada panel es una columna que recorta lo que se sale: dale `grow=1` a su
    contenido (un `scroll`, por ejemplo) para que lo rellene. Para los lectores
    de pantalla, el separador es un `"separator"` enfocable con el tamaño como
    valor; su key es `f"{key}-handle"`. Los `estilo` van al contenedor, que por
    defecto crece (`grow=1`).
    """
    if direction not in ("row", "column"):
        raise ValueError('direction debe ser "row" o "column"')
    if isinstance(size, Signal):
        value = size
        k = key or f"splitter-{id(size)}"
    else:
        if key is None:
            raise ValueError("splitter necesita una key si size no es un Signal")
        k = key
        value = _SPLITS.setdefault(k, Signal(float(size)))
    min_first, min_second = (float(m) for m in min_sizes)
    row = direction == "row"
    dim = "width" if row else "height"
    measured = _EXTENTS.setdefault(k, Signal(None))
    extent = measured()
    low = min_first
    high = max(low, extent - _HANDLE - min_second) if extent is not None else None

    def clamp(v: float) -> float:
        v = max(low, v)
        return min(high, v) if high is not None else v

    shown = clamp(float(value()))

    def set_size(v: float) -> None:
        v = clamp(float(v))
        if v != value():
            value.set(v)
            if on_change is not None:
                on_change(v)

    def on_resize(e: Any) -> None:
        # Cambiarlo reconstruye la vista: los límites dependen de él.
        measured.set(e.width if row else e.height)

    def on_drag(e: Any) -> None:
        if e.phase == "start":
            _DRAG_START[k] = shown
            return
        start = _DRAG_START.get(k)
        if start is None:
            return
        set_size(start + (e.dx if row else e.dy))
        if e.phase == "end":
            _DRAG_START.pop(k, None)

    def on_key(e: Any) -> bool | None:
        less, more = ("ArrowLeft", "ArrowRight") if row else ("ArrowUp", "ArrowDown")
        if e.key == less:
            set_size(shown - step)
        elif e.key == more:
            set_size(shown + step)
        elif e.key == "Home":
            set_size(low)
        elif e.key == "End" and high is not None:
            set_size(high)
        else:
            return None
        return True

    line = box(grow=1, bg="$border", **{"width" if row else "height": 1})
    handle = box(
        key=f"{k}-handle",
        direction="column" if row else "row",
        align="center",
        shrink=0,
        cursor="col-resize" if row else "row-resize",
        bg_hover="$glow",
        bg_pressed="$glow",
        focusable=True,
        on_drag=on_drag,
        on_key=on_key,
        on_value=set_size,
        role="separator",
        orientation="vertical" if row else "horizontal",
        label="Redimensionar paneles",
        value=shown,
        value_min=low,
        value_max=high,
        value_step=step,
        **{dim: _HANDLE},
    )[line]
    pane_first = box(key=f"{k}-first", shrink=1, overflow="hidden", **{dim: shown, f"min_{dim}": min_first})[
        first
    ]
    pane_second = box(key=f"{k}-second", grow=1, overflow="hidden", **{dim: 0, f"min_{dim}": min_second})[
        second
    ]
    return box(**{"key": k, "direction": direction, "grow": 1, "on_resize": on_resize, **style})[
        pane_first, handle, pane_second
    ]
