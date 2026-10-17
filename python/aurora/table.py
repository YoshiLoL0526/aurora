"""Tabla de datos: cabecera fija, ordenación, columnas redimensionables y filas virtualizadas.

Se compone en Python con primitivas: las filas son una `virtual_list` (solo se
construyen las visibles) y el redimensionado usa `on_drag` sobre el borde de
cada cabecera. El núcleo no sabe nada de tablas.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ._core import DragEvent
from ._icons import _ARROW_DOWN, _ARROW_UP
from .components import divider, virtual_list
from .elements import Element, box, column, image, row, scroll, text
from .signal import Signal

Sort = tuple[str, bool] | None
"""Orden de una tabla: `(key de la columna, descendente)`, o `None` (orden original)."""

Align = Literal["start", "center", "end"]


@dataclass(frozen=True)
class Column:
    """Columna de una `table`.

    El valor de cada celda sale de `value(fila)` o, si no se indica, de la fila
    misma: `fila[key]` en un dict, `getattr(fila, key)` en un objeto o la posición
    de la columna en una tupla o lista. Ese valor es el que se ordena y, pasado por
    `format` (o `str`), el que se muestra. `cell(fila)` sustituye el texto por
    cualquier elemento.
    """

    key: str
    title: str | None = None
    width: float = 160
    min_width: float = 48
    align: Align = "start"
    value: Callable[[Any], Any] | None = None
    format: Callable[[Any], str] | None = None
    cell: Callable[[Any], Element] | None = None
    sortable: bool = True
    resizable: bool = True


# Estado de cada tabla, por key (los componentes no tienen estado propio).
_SORTS: dict[str, Signal[Sort]] = {}
_WIDTHS: dict[str, Signal[dict[str, float]]] = {}
# Ancho de la columna al empezar a arrastrar su borde.
_GRAB: dict[tuple[str, str], float] = {}
# Último orden calculado de cada tabla: (filas, número de filas, orden, índices).
_ORDERS: dict[str, tuple[Sequence[Any], int, Sort, list[int]]] = {}

_RESIZE_HANDLE = 8


def _value(col: Column, index: int, item: Any) -> Any:
    if col.value is not None:
        return col.value(item)
    if isinstance(item, Mapping):
        return item.get(col.key)
    if isinstance(item, (tuple, list)):
        return item[index] if index < len(item) else None
    return getattr(item, col.key, None)


def _sort_key(v: Any) -> Any:
    return v.casefold() if isinstance(v, str) else v


def _order(key: str, rows: Sequence[Any], cols: list[Column], sort: Sort) -> list[int] | None:
    """Índices de `rows` en el orden pedido (`None`: el original). Los vacíos (`None`)
    van siempre al final y los empates conservan el orden original. Se memoriza:
    desplazarse o redimensionar no vuelve a ordenar."""
    if sort is None:
        return None
    cached = _ORDERS.get(key)
    if cached is not None and cached[0] is rows and cached[1] == len(rows) and cached[2] == sort:
        return cached[3]
    by, descending = sort
    index = next((i for i, c in enumerate(cols) if c.key == by), None)
    if index is None:
        return None
    col = cols[index]
    values = [_value(col, index, item) for item in rows]
    present = [i for i, v in enumerate(values) if v is not None]
    missing = [i for i, v in enumerate(values) if v is None]
    try:
        present.sort(key=lambda i: _sort_key(values[i]), reverse=descending)
    except TypeError:  # tipos mezclados que no se comparan: por tipo y texto
        present.sort(key=lambda i: (type(values[i]).__name__, str(values[i])), reverse=descending)
    order = present + missing
    _ORDERS[key] = (rows, len(rows), sort, order)
    return order


def table(
    rows: Sequence[Any],
    columns: Sequence[Column | str],
    *,
    key: str,
    sort: Signal[Sort] | None = None,
    widths: Signal[dict[str, float]] | None = None,
    on_row_click: Callable[[Any], Any] | None = None,
    row_height: float = 36,
    header_height: float = 40,
    striped: bool = True,
    empty: str = "Sin datos",
    overscan: int = 4,
    **style: Any,
) -> Element:
    """Tabla de datos con cabecera fija y filas virtualizadas.

    `rows` es cualquier secuencia (dicts, tuplas, dataclasses…) y `columns`, objetos
    `Column` o simplemente keys. Solo se construyen las filas visibles, así que
    admite cientos de miles. Pulsar una cabecera ordena por esa columna
    (ascendente → descendente → original) y arrastrar su borde derecho cambia su
    ancho. El orden y los anchos se guardan por `key`; pasa tus propios `Signal`
    en `sort` (`(columna, descendente)` o `None`) y `widths` (`{columna: ancho}`)
    para leerlos o fijarlos desde fuera.

    El orden se memoriza mientras `rows` sea el mismo objeto: si cambian los datos,
    pasa una secuencia nueva (no la modifiques en su sitio).
    """
    cols = [c if isinstance(c, Column) else Column(c) for c in columns]
    sort_ = sort if sort is not None else _SORTS.setdefault(key, Signal(None))
    widths_ = widths if widths is not None else _WIDTHS.setdefault(key, Signal({}))
    current = sort_()
    sized = widths_()
    width = {c.key: max(c.min_width, sized.get(c.key, c.width)) for c in cols}
    total = sum(width.values())
    order = _order(key, rows, cols, current)

    def toggle(col: Column) -> None:
        if current is None or current[0] != col.key:
            sort_.set((col.key, False))
        elif not current[1]:
            sort_.set((col.key, True))
        else:
            sort_.set(None)

    def resize(col: Column, e: DragEvent) -> None:
        grab = (key, col.key)
        if e.phase == "start":
            _GRAB[grab] = width[col.key]
        base = _GRAB.get(grab, width[col.key])
        if e.phase == "end":
            _GRAB.pop(grab, None)
        widths_.set({**widths_(), col.key: max(col.min_width, round(base + e.dx))})

    def header(col: Column) -> Element:
        sorted_by = current is not None and current[0] == col.key
        descending = current is not None and current[1]
        arrow = sorted_by and image(_ARROW_DOWN if descending else _ARROW_UP, width=12)
        label = text(
            col.title if col.title is not None else col.key,
            size=12,
            weight=600,
            color="$text" if sorted_by else "$muted",
            letter_spacing=0.3,
            max_lines=1,
            shrink=1,
        )
        handle = (
            col.resizable
            and box(
                key=f"{key}/resize/{col.key}",
                position="absolute",
                top=0,
                bottom=0,
                right=0,
                width=_RESIZE_HANDLE,
                align="center",
                justify="center",
                cursor="col-resize",
                bg_hover="$surface_pressed",
                on_drag=lambda e: resize(col, e),
            )[box(width=1, height=header_height / 2, bg="$border")]
        )
        return row(
            key=f"{key}/h/{col.key}",
            width=width[col.key],
            shrink=0,
            height=header_height,
            gap=4,
            align="center",
            justify=col.align,
            padding=(0, 12),
            bg_hover="$surface_hover" if col.sortable else None,
            on_click=(lambda: toggle(col)) if col.sortable else None,
        )[
            col.align == "end" and arrow,
            label,
            col.align != "end" and arrow,
            handle,
        ]

    def cell(col: Column, index: int, item: Any) -> Element:
        if col.cell is not None:
            content = col.cell(item)
        else:
            value = _value(col, index, item)
            shown = "" if value is None else col.format(value) if col.format else str(value)
            content = text(shown, max_lines=1, shrink=1)
        return row(
            width=width[col.key],
            shrink=0,
            height=row_height,
            align="center",
            justify=col.align,
            padding=(0, 12),
        )[content]

    def body_row(position: int) -> Element:
        index = order[position] if order is not None else position
        item = rows[index]
        click = on_row_click
        return row(
            key=f"{key}/row/{index}",
            grow=1,
            align="center",
            bg="$surface_hover" if striped and position % 2 else None,
            bg_hover="$surface_pressed" if click else None,
            focusable=False,
            on_click=(lambda: click(item)) if click else None,
        )[[cell(col, i, item) for i, col in enumerate(cols)]]

    body = (
        virtual_list(
            len(rows), body_row, item_height=row_height, key=f"{key}/body", overscan=overscan, min_height=0
        )
        if rows
        else column(grow=1, align="center", justify="center", padding=24)[text(empty, color="$muted")]
    )
    # Como en CSS, una caja flexible no encoge por debajo de su contenido salvo con un
    # mínimo explícito: sin él, la tabla mediría el alto de todas las filas y la lista
    # virtual las construiría todas. El mínimo por defecto deja ver unas pocas filas.
    defaults: dict[str, Any] = {
        "bg": "$surface",
        "radius": "$lg",
        "border_width": 1,
        "border_color": "$border",
        "min_height": header_height + 1 + 3 * row_height,
    }
    if "height" not in style and "max_height" not in style:
        defaults["grow"] = 1
    return column(key=key, **{**defaults, **style})[
        scroll(axis="x", key=f"{key}/x", grow=1, min_height=0, radius="$lg")[
            column(grow=1, min_width=total, min_height=0)[
                row(height=header_height, shrink=0)[[header(c) for c in cols]],
                divider(),
                body,
            ]
        ]
    ]
