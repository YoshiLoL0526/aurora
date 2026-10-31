"""Arrastrar y soltar dentro de la app: `sortable` (listas reordenables y tableros kanban).

El núcleo solo aporta lo que Python no puede saber: bajo qué zona de soltar
(`drop_target=True`) está el puntero y en qué posición caería entre sus hijos
arrastrables (`DragEvent.target` y `DragEvent.index`). Todo lo demás —el umbral
que separa un clic de un arrastre, la vista previa que sigue al puntero, el
indicador, el teclado y los anuncios para el lector de pantalla— vive aquí.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Generic, Literal, TypeVar, overload

from ..elements import Child, Element, TextLike, box, text
from ..signal import Signal
from ._state import _ANNOUNCE, _DRAGS, _ZONES

T = TypeVar("T")

# Distancia (px lógicos) que tiene que recorrer el puntero para que una pulsación
# sea un arrastre y no un clic.
_THRESHOLD = 4.0
# Orden de construcción de las listas: el de las flechas laterales del teclado.
_SEQUENCE = itertools.count()


@dataclass(frozen=True, slots=True)
class MoveEvent(Generic[T]):
    """Lo que recibe `on_move` de un `sortable` al soltar un elemento en otro sitio.

    `item` es el elemento movido; `source` y `target`, las `key` de la lista de
    origen y la de destino (la misma si se reordena); `source_index`, dónde
    estaba, e `index`, dónde queda en la lista de destino una vez quitado de la
    de origen. `apply(...)` hace el movimiento sobre tus datos.
    """

    item: T
    source: str
    source_index: int
    target: str
    index: int

    @overload
    def apply(self, lists: Sequence[T]) -> list[T]: ...
    @overload
    def apply(self, lists: Mapping[str, Sequence[T]]) -> dict[str, list[T]]: ...
    def apply(self, lists: Sequence[T] | Mapping[str, Sequence[T]]) -> list[T] | dict[str, list[T]]:
        """Devuelve una copia de los datos con el movimiento hecho (no cambia los originales).

        Con una lista (reordenar una sola `sortable`), la lista nueva; con un
        dict de `key` de lista → elementos (un tablero), el dict nuevo.
        """
        if isinstance(lists, Mapping):
            out = {name: list(values) for name, values in lists.items()}
            moved = out[self.source].pop(self.source_index)
            out[self.target].insert(self.index, moved)
            return out
        if self.source != self.target:
            raise ValueError("con una sola lista, el movimiento debe ser dentro de ella; usa un dict")
        values = list(lists)
        values.insert(self.index, values.pop(self.source_index))
        return values


@dataclass(frozen=True, slots=True)
class _Drag:
    """Arrastre en curso en un grupo: qué se mueve y dónde caería."""

    item: Any
    ident: Hashable
    source: str
    source_index: int
    target: str | None
    index: int | None
    dx: float = 0.0
    dy: float = 0.0
    keyboard: bool = False


@dataclass(slots=True)
class _Zone:
    """Una `sortable` construida, tal como la necesitan el teclado y el soltar."""

    key: str
    items: list[Any]
    idents: list[Hashable]
    names: list[str]
    label: str
    on_move: Callable[[MoveEvent[Any]], Any] | None
    seq: int


def _plain(value: TextLike) -> str:
    return str(value() if callable(value) else value)


def _ident_key(ident: Hashable) -> str:
    if isinstance(ident, tuple):
        return "/".join(str(part) for part in ident)
    return str(ident)


def sortable(
    items: Sequence[T],
    item: Callable[[T], Element],
    *,
    key: str,
    group: str | None = None,
    ident: Callable[[T], Hashable] | None = None,
    item_label: Callable[[T], TextLike] = str,
    on_move: Callable[[MoveEvent[T]], Any] | None = None,
    direction: Literal["column", "row"] = "column",
    gap: float = 8,
    empty: Child = None,
    **style: Any,
) -> Element:
    """Lista cuyos elementos se reordenan arrastrándolos (o con el teclado).

    `item(valor)` construye cada elemento. Al soltar uno en otra posición se
    llama a `on_move(evento)` con un `MoveEvent` (elemento, lista de origen y
    de destino, y posiciones): la lista no cambia sola, la cambias tú —
    `evento.apply(...)` hace el movimiento sobre tus datos—. Las `sortable` con
    el mismo `group` forman un tablero: los elementos pasan de una a otra (se
    llama una vez, al `on_move` de la de destino o, si no tiene, al de la de
    origen).

    Mientras se arrastra, el elemento sigue al puntero por encima de todo y una
    línea marca dónde caerá (en una lista vacía, se resalta la lista). Un clic
    sin mover no arrastra: los botones de dentro de un elemento siguen
    funcionando.

    Con el teclado: Espacio o Enter sobre un elemento enfocado lo coge, las
    flechas del eje de la lista lo mueven, las del otro eje lo pasan a la lista
    anterior o siguiente del grupo, Espacio o Enter lo sueltan y Esc cancela.
    Cada paso se anuncia al lector de pantalla.

    `ident(valor)` identifica cada elemento (por defecto, el propio valor, que
    debe ser hashable); su key es `f"{grupo}:{identidad}"`, así que el foco lo
    sigue de una lista a otra. `item_label(valor)` es el nombre con que se
    anuncia. `direction="row"` la pone en fila. `empty` (un texto o un
    elemento) se muestra dentro de la lista cuando no tiene elementos: sigue
    siendo una zona donde soltar. Para los lectores de pantalla
    es una `"list"` de `"listitem"`s; dale un `label` para que los anuncios
    digan a qué lista va cada elemento.
    """
    group = key if group is None else group
    ident_of: Callable[[T], Hashable] = ident if ident is not None else (lambda value: value)  # ty: ignore[invalid-assignment]
    drag = _DRAGS.setdefault(group, Signal(None))
    announce = _ANNOUNCE.setdefault(group, Signal(("", "")))
    values = list(items)
    idents = [ident_of(v) for v in values]
    zone_label = _plain(style.get("label") or key)
    zones = _ZONES.setdefault(group, {})
    zones[key] = _Zone(
        key, values, idents, [_plain(item_label(v)) for v in values], zone_label, on_move, next(_SEQUENCE)
    )
    state = drag()
    row_axis = direction == "row"

    def say(zone: str, message: str) -> None:
        announce.set((zone, message))

    def position(zone: _Zone, index: int, moving: Hashable) -> str:
        count = len([i for i in zone.idents if i != moving]) + 1
        return f"posición {index + 1} de {count} en «{zone.label}»"

    def ordered() -> list[_Zone]:
        return sorted(zones.values(), key=lambda z: z.seq)

    def finish(current: _Drag) -> None:
        """Suelta: avisa a las listas si el elemento cambió de sitio."""
        drag.set(None)
        target = zones.get(current.target) if current.target is not None else None
        source = zones.get(current.source)
        name = _ident_name(current)
        if target is None or source is None or current.index is None:
            say(current.source, f"Cancelado. «{name}» vuelve a su sitio.")
            return
        say(target.key, f"«{name}» soltado en {position(target, current.index, current.ident)}.")
        if target.key == source.key and current.index == current.source_index:
            return
        event = MoveEvent(current.item, source.key, current.source_index, target.key, current.index)
        handler = target.on_move if target.on_move is not None else source.on_move
        if handler is not None:
            handler(event)

    def _ident_name(current: _Drag) -> str:
        zone = zones.get(current.source)
        if zone is not None and current.ident in zone.idents:
            return zone.names[zone.idents.index(current.ident)]
        return _ident_key(current.ident)

    def targets(target: Any, index: Any) -> tuple[str | None, int | None]:
        """La zona del núcleo, si es una lista de este grupo."""
        if isinstance(target, str) and target in zones and index is not None:
            return target, int(index)
        return None, None

    def make_drag(i: int, value: T) -> Callable[[Any], None]:
        me = idents[i]

        def on_drag(e: Any) -> None:
            current = drag()
            mine = current is not None and current.ident == me and not current.keyboard
            if e.phase == "start":
                return
            if not mine:
                # Hasta pasar el umbral es un clic: no se arrastra nada.
                if e.phase != "move" or (e.dx * e.dx + e.dy * e.dy) < _THRESHOLD * _THRESHOLD:
                    return
                current = _Drag(value, me, key, i, None, None)
                say(key, f"«{zones[key].names[i]}» cogido.")
            assert current is not None
            target, index = targets(e.target, e.index)
            current = replace(current, dx=e.dx, dy=e.dy, target=target, index=index)
            if e.phase == "end":
                finish(current)
            else:
                drag.set(current)

        return on_drag

    def make_key(i: int, value: T) -> Callable[[Any], bool | None]:
        me = idents[i]

        def on_key(e: Any) -> bool | None:
            current = drag()
            holding = current is not None and current.keyboard and current.ident == me
            if not holding:
                if e.key in (" ", "Space", "Enter") and current is None:
                    drag.set(_Drag(value, me, key, i, key, i, keyboard=True))
                    here = zones[key]
                    say(
                        key,
                        f"«{here.names[i]}» cogido, {position(here, i, me)}. Muévelo con las flechas, "
                        "suéltalo con Espacio y cancela con Esc.",
                    )
                    return True
                return None
            assert current is not None
            if e.key in (" ", "Space", "Enter"):
                finish(current)
                return True
            if e.key == "Escape":
                drag.set(None)
                say(current.source, f"Cancelado. «{_ident_name(current)}» vuelve a su sitio.")
                return True
            along = ("ArrowLeft", "ArrowRight") if row_axis else ("ArrowUp", "ArrowDown")
            across = ("ArrowUp", "ArrowDown") if row_axis else ("ArrowLeft", "ArrowRight")
            zone = zones.get(current.target or current.source)
            if zone is None:
                return None
            room = len([x for x in zone.idents if x != me])
            index = current.index if current.index is not None else 0
            if e.key in along:
                index = max(0, min(room, index + (1 if e.key == along[1] else -1)))
            elif e.key in across:
                order = ordered()
                at = next((n for n, z in enumerate(order) if z.key == zone.key), 0)
                step = 1 if e.key == across[1] else -1
                if not 0 <= at + step < len(order):
                    return True
                zone = order[at + step]
                index = min(index, len([x for x in zone.idents if x != me]))
            else:
                return None
            drag.set(replace(current, target=zone.key, index=index))
            say(zone.key, f"«{_ident_name(current)}», {position(zone, index, me)}.")
            return True

        return on_key

    # Dónde va el indicador: antes del elemento `index` de los que quedan (o tras el último).
    dragging = state is not None and state.ident in idents and state.source == key
    marker: tuple[Hashable, Literal["before", "after"]] | None = None
    empty_target = False
    if state is not None and state.target == key and state.index is not None:
        rest = [x for x in idents if x != state.ident]
        if not rest:
            empty_target = True
        elif state.index < len(rest):
            marker = (rest[state.index], "before")
        else:
            marker = (rest[-1], "after")

    def line(where: Literal["before", "after"]) -> Element:
        offset = -(gap / 2) - 1
        edge = {"top" if where == "before" else "bottom": offset} if not row_axis else {}
        side = {"left" if where == "before" else "right": offset} if row_axis else {}
        size = {"width": 2, "top": 0, "bottom": 0} if row_axis else {"height": 2, "left": 0, "right": 0}
        return box(position="absolute", radius=1, bg="$primary", hidden=True, **size, **edge, **side)

    def wrap(i: int, value: T) -> Element:
        me = idents[i]
        lifted = dragging and state is not None and state.ident == me and not state.keyboard
        held = state is not None and state.ident == me and state.keyboard
        lift: dict[str, Any] = {}
        if lifted and state is not None:
            lift = dict(
                layer="overlay", top=state.dy, left=state.dx, opacity=0.92, shadow=(0, 12, 28, "$shadow")
            )
        elif held:
            lift = dict(border_width=2, border_color="$primary", radius="$sm")
        return box(
            key=f"{group}:{_ident_key(me)}",
            on_drag=make_drag(i, value),
            on_key=make_key(i, value),
            focusable=True,
            cursor="grabbing" if lifted else "grab",
            role="listitem",
            label=zones[key].names[i],
            description="Espacio para mover",
            position_in_set=i + 1,
            set_size=len(values),
            selected=True if held else None,
            **lift,
        )[
            item(value),
            marker is not None and marker[0] == me and line(marker[1]),
        ]

    zone_name, message = announce()
    highlight = {"bg": "$glow"} if empty_target else {}
    return box(
        key=key,
        direction=direction,
        gap=gap,
        drop_target=True,
        role="list",
        **{"min_height": 48, "radius": "$sm", **style, **highlight},
    )[
        [wrap(i, v) for i, v in enumerate(values)],
        not values and empty,
        # Región viva: los anuncios salen de la lista donde está ahora el elemento.
        text(
            message if zone_name == key else "",
            live="assertive",
            position="absolute",
            width=1,
            height=1,
            overflow="hidden",
            opacity=0,
        ),
    ]
