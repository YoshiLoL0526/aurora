"""Listas virtualizadas (solo construyen las filas visibles): `virtual_list` y `tree`."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from .._icons import _CHEVRON, _CHEVRON_RIGHT
from ..elements import Element, TextLike, box, column, image, row, scroll, text
from ..signal import Signal
from ._state import _HEIGHTS, _TREE_OPEN, _TREE_SELECTED, _VIEWPORTS

N = TypeVar("N")

# Alto que se supone visible hasta el primer frame, cuando el núcleo lo mide.
_GUESSED_HEIGHT = 1080.0


def virtual_list(
    count: int,
    item: Callable[[int], Element],
    *,
    item_height: float | None = None,
    estimated_height: float = 40,
    key: str,
    gap: float = 0,
    overscan: int = 4,
    stick_to_end: bool = False,
    role: str = "list",
    item_role: str = "listitem",
    **style: Any,
) -> Element:
    """Lista desplazable de `count` filas que solo construye las visibles.

    `item(i)` devuelve la fila `i`. Con `item_height`, todas las filas miden eso
    (más `gap` entre ellas), así que la lista sabe su alto total y qué filas caen en
    la zona visible sin construirlas: con 100 000 filas, cada reconstrucción crea unas
    pocas decenas. Se reconstruye al desplazarse solo cuando cambia el rango visible;
    `overscan` filas de más por cada lado cubren el desplazamiento entre medias. Cada
    fila ocupa un hueco de todo el ancho y `item_height` de alto: dale `grow=1` a su
    raíz para que lo rellene.

    Sin `item_height`, cada fila mide lo que pida su contenido (mensajes, tarjetas):
    las que no se han visto aún se suponen de `estimated_height` y, al construirse,
    el layout las mide y la lista corrige su alto total sin que salte lo que se está
    viendo. Cuanto más se acerque la estimación a la media, más fiel es la barra.

    `stick_to_end=True` empieza al final y, mientras se esté al final, lo sigue
    cuando llegan filas nuevas (un chat, un registro).

    `key` es obligatoria: guarda la posición, la zona visible y los altos medidos
    (por índice). Con `@component`, las filas que siguen visibles no se reconstruyen.
    Para los lectores de pantalla es una `"list"` de `"listitem"`s (con su posición);
    `table` cambia esos roles con `role`/`item_role`.
    """
    row_props = lambda i: {"role": item_role, "position_in_set": i + 1, "set_size": count}
    if item_height is None:
        return _variable(
            count,
            item,
            estimated=estimated_height,
            key=key,
            gap=gap,
            overscan=overscan,
            role=role,
            row_props=row_props,
            stick_to_end=stick_to_end,
            **style,
        )
    if stick_to_end:
        style["stick_to_end"] = True
    return _virtual(
        count,
        item,
        item_height=item_height,
        key=key,
        gap=gap,
        overscan=overscan,
        role=role,
        row_props=row_props,
        **style,
    )


def _virtual(
    count: int,
    item: Callable[[int], Element],
    *,
    item_height: float,
    key: str,
    gap: float,
    overscan: int,
    role: str,
    row_props: Callable[[int], dict[str, Any]],
    **style: Any,
) -> Element:
    """`virtual_list` con las propiedades de cada hueco a medida (`row_props(i)`):
    `tree` no anuncia los huecos sino sus filas."""
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
        column(
            key=f"{key}#{i}",
            position="absolute",
            top=i * stride,
            left=0,
            right=0,
            height=item_height,
            **row_props(i),
        )[item(i)]
        for i in range(first, last)
    ]
    return scroll(key=key, on_scroll=on_scroll, role=role, **style)[box(height=total, shrink=0)[rows]]


class _Heights:
    """Altos medidos de las filas de una `virtual_list` de alto variable.

    Guarda, por fila, cuánto difiere su alto medido del estimado en un árbol de
    Fenwick: el inicio de la fila `i` es `i` filas estimadas más la suma de las
    diferencias de las anteriores, en O(log n), y medir una fila cuesta lo mismo.
    """

    __slots__ = ("diff", "tree", "version")

    def __init__(self) -> None:
        self.tree = [0.0]  # tree[i] (desde 1) suma las diferencias de (i - i&-i, i]
        self.diff: dict[int, float] = {}
        self.version = Signal(0)

    def resize(self, count: int) -> None:
        n = len(self.tree) - 1
        if count < n:
            # Cada nodo solo depende de los anteriores: recortar sigue siendo válido.
            del self.tree[count + 1 :]
            self.diff = {i: d for i, d in self.diff.items() if i < count}
        elif count - n <= 64:
            # Pocas filas nuevas (un chat que crece): se añaden en O(log n) cada una.
            for i in range(n + 1, count + 1):
                self.tree.append(self.before(i - 1) - self.before(i - (i & -i)))
        else:
            self.tree = [0.0] * (count + 1)
            for i, d in self.diff.items():
                self._add(i, d)

    def _add(self, i: int, d: float) -> None:
        i += 1
        while i < len(self.tree):
            self.tree[i] += d
            i += i & -i

    def before(self, i: int) -> float:
        """Suma de las diferencias de las filas anteriores a `i`."""
        total = 0.0
        while i > 0:
            total += self.tree[i]
            i -= i & -i
        return total

    def measure(self, i: int, diff: float) -> None:
        """Apunta la diferencia medida de la fila `i`; si cambia, la lista se reconstruye."""
        old = self.diff.get(i, 0.0)
        if i < len(self.tree) - 1 and abs(diff - old) >= 0.5:
            self.diff[i] = diff
            self._add(i, diff - old)
            self.version.set(self.version() + 1)


def _variable(
    count: int,
    item: Callable[[int], Element],
    *,
    estimated: float,
    key: str,
    gap: float,
    overscan: int,
    role: str,
    row_props: Callable[[int], dict[str, Any]],
    stick_to_end: bool,
    **style: Any,
) -> Element:
    """`virtual_list` sin `item_height`: las filas van en flujo y se miden al maquetarse.
    Las que no se ven las sustituyen dos rellenos con su alto (medido o estimado), y el
    núcleo mantiene quieto lo que se ve (`scroll_anchor`) cuando cambian."""
    if estimated <= 0:
        raise ValueError("estimated_height debe ser positivo")
    viewport = _VIEWPORTS.setdefault(key, Signal(None))
    heights: _Heights = _HEIGHTS.setdefault(key, _Heights())
    heights.version()
    heights.resize(count)
    stride = estimated + gap

    def start(i: int) -> float:
        """Dónde empieza la fila `i` (o, con `i == count`, el final más un `gap`)."""
        return i * stride + heights.before(i)

    def index_at(y: float) -> int:
        """La fila que ocupa la altura `y` del contenido."""
        lo, hi = 0, count
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if start(mid) <= y:
                lo = mid
            else:
                hi = mid - 1
        return lo

    def visible(y: float, height: float) -> tuple[int, int]:
        first = max(0, index_at(y) - overscan)
        last = min(count, index_at(y + height) + 1 + overscan)
        return first, max(first, last)

    def on_scroll(e: Any) -> None:
        current = viewport()
        if current is None or visible(*current) != visible(e.y, e.height):
            viewport.set((e.y, e.height))

    def measured(i: int) -> Callable[[Any], None]:
        return lambda e: heights.measure(i, e.height - estimated)

    first, last = visible(*(viewport() or (0.0, _GUESSED_HEIGHT)))
    total = max(0.0, start(count) - gap)
    rows = [
        column(key=f"{key}#{i}", shrink=0, on_resize=measured(i), **row_props(i))[item(i)]
        for i in range(first, last)
    ]
    # Lo que no se construye, arriba y abajo, lo ocupan los rellenos.
    content = (
        column(gap=gap, shrink=0, padding=(start(first), 0, start(count) - start(last), 0))[rows]
        if rows
        else box(height=total, shrink=0)
    )
    return scroll(
        key=key,
        on_scroll=on_scroll,
        role=role,
        scroll_anchor=True,
        stick_to_end=stick_to_end,
        **style,
    )[content]


@dataclass(frozen=True, slots=True)
class _Row(Generic[N]):
    """Fila visible de un `tree`: el nodo y dónde está."""

    node: N
    ident: Hashable
    level: int
    parent: int  # índice de la fila del padre (-1 en el primer nivel)
    position: int  # posición entre sus hermanos (desde 1)
    siblings: int
    branch: bool  # tiene hijos


def _ident_key(ident: Hashable) -> str:
    """Parte de la key de una fila: la ruta `("src", "main.py")` se escribe `src/main.py`."""
    if isinstance(ident, tuple):
        return "/".join(str(part) for part in ident)
    return str(ident)


def _plain(value: TextLike) -> str:
    return str(value() if callable(value) else value)


def tree(
    roots: Sequence[N],
    children: Callable[[N], Sequence[N]],
    *,
    key: str,
    label: Callable[[N], TextLike] = str,
    ident: Callable[[N], Hashable] | None = None,
    expanded: Signal[set[Any]] | None = None,
    selected: Signal[Any] | None = None,
    icon: Callable[[N], Element | None] | None = None,
    on_select: Callable[[N], Any] | None = None,
    on_activate: Callable[[N], Any] | None = None,
    item_height: float = 30,
    indent: float = 18,
    overscan: int = 4,
    **style: Any,
) -> Element:
    """Árbol expandible y virtualizado: carpetas que se despliegan, con selección y teclado.

    `roots` son los nodos de primer nivel y `children(nodo)` devuelve los hijos
    de un nodo (vacío en las hojas); solo se pide para los nodos visibles, así
    que puede cargarlos bajo demanda. `label(nodo)` es su texto e `icon(nodo)`,
    opcional, un elemento delante de él. Cada nodo se identifica con
    `ident(nodo)`, que debe ser único y estable (por defecto, la tupla de
    etiquetas desde la raíz: `("src", "main.py")`).

    `expanded` guarda el conjunto de identidades desplegadas y `selected` la del
    nodo elegido (o `None`): pásalos como `Signal` para leerlos o cambiarlos
    desde fuera; sin ellos, el estado vive en la `key`. Un clic elige la fila y
    el triángulo la despliega o la pliega. `on_select(nodo)` se llama al elegir
    y `on_activate(nodo)` al pulsar Enter.

    Con el árbol enfocado, ↑/↓ recorren las filas visibles, → despliega (o baja
    al primer hijo), ← pliega (o sube al padre), Inicio/Fin van a la primera y a
    la última fila, y Enter llama a `on_activate` (sin él, despliega o pliega).
    La fila elegida siempre queda a la vista.

    Como una `virtual_list`, solo construye las filas visibles (todas miden
    `item_height`), así que escala a árboles con decenas de miles de nodos
    desplegados; ocupa el espacio libre (o dale `height`/`max_height`). Para los
    lectores de pantalla es un `"tree"` de `"treeitem"`s con su nivel, su
    posición entre hermanos y si están desplegados. Las filas tienen la key
    `f"{key}-{identidad}"` (una tupla se une con `/`).
    """
    if item_height <= 0:
        raise ValueError("item_height debe ser positivo")
    if indent < 0:
        raise ValueError("indent no puede ser negativo")
    opened = expanded if expanded is not None else _TREE_OPEN.setdefault(key, Signal(set()))
    chosen = selected if selected is not None else _TREE_SELECTED.setdefault(key, Signal(None))
    open_ids = opened()
    current = chosen()

    # Filas visibles, en orden: un recorrido en profundidad que solo baja por lo desplegado.
    rows: list[_Row[N]] = []
    stack: list[tuple[Sequence[N], int, int, tuple[str, ...], int]] = [(roots, 0, -1, (), 0)]
    while stack:
        nodes, level, parent, path, i = stack.pop()
        if i >= len(nodes):
            continue
        stack.append((nodes, level, parent, path, i + 1))
        node = nodes[i]
        here = (*path, _plain(label(node)))
        kids = children(node)
        node_id = ident(node) if ident is not None else here
        rows.append(_Row(node, node_id, level, parent, i + 1, len(nodes), bool(kids)))
        if kids and node_id in open_ids:
            stack.append((kids, level + 1, len(rows) - 1, here, 0))

    index = next((i for i, r in enumerate(rows) if r.ident == current), -1)

    def toggle(r: _Row[N]) -> None:
        opened.set(set(opened()) ^ {r.ident})

    def choose(i: int) -> None:
        r = rows[i]
        if r.ident != chosen():
            chosen.set(r.ident)
            if on_select is not None:
                on_select(r.node)

    def on_key(e: Any) -> bool | None:
        if not rows:
            return None
        at = max(index, 0)
        r = rows[at]
        if e.key == "ArrowDown":
            choose(min(len(rows) - 1, at + 1) if index >= 0 else 0)
        elif e.key == "ArrowUp":
            choose(max(0, at - 1))
        elif e.key == "Home":
            choose(0)
        elif e.key == "End":
            choose(len(rows) - 1)
        elif e.key == "ArrowRight":
            if r.branch and r.ident not in open_ids:
                toggle(r)
            elif r.branch and at + 1 < len(rows):
                choose(at + 1)
        elif e.key == "ArrowLeft":
            if r.branch and r.ident in open_ids:
                toggle(r)
            elif r.parent >= 0:
                choose(r.parent)
        elif e.key == "Enter" and index >= 0:
            if on_activate is not None:
                on_activate(r.node)
            elif r.branch:
                toggle(r)
        else:
            return None
        return True

    def item(i: int) -> Element:
        r = rows[i]
        is_open = r.branch and r.ident in open_ids
        is_chosen = i == index
        name = label(r.node)
        arrow = box(
            width=16,
            height=16,
            align="center",
            justify="center",
            shrink=0,
            radius=4,
            focusable=False,
            hidden=True,
            **({"on_click": lambda: toggle(r), "bg_hover": "$border"} if r.branch else {}),
        )[r.branch and image(_CHEVRON if is_open else _CHEVRON_RIGHT, width=12)]
        return row(
            key=f"{key}-{_ident_key(r.ident)}",
            grow=1,
            gap=6,
            align="center",
            padding=(0, 8, 0, 6 + r.level * indent),
            radius=6,
            bg="$glow" if is_chosen else "#00000000",
            bg_hover="$glow" if is_chosen else "$surface_hover",
            # El foco se queda en el árbol: las filas aparecen y desaparecen al desplazarse.
            focusable=False,
            on_click=lambda: choose(i),
            role="treeitem",
            label=_plain(name),
            level=r.level + 1,
            expanded=is_open if r.branch else None,
            selected=is_chosen,
            position_in_set=r.position,
            set_size=r.siblings,
        )[
            arrow,
            icon(r.node) if icon is not None else None,
            text(name, size=13, weight=600 if is_chosen else 400, max_lines=1, hidden=True),
        ]

    reveal = (index * item_height, (index + 1) * item_height) if index >= 0 else None
    return _virtual(
        len(rows),
        item,
        item_height=item_height,
        key=key,
        gap=0,
        overscan=overscan,
        role="tree",
        row_props=lambda i: {},
        **{"focusable": True, "on_key": on_key, "reveal": reveal, **style},
    )
