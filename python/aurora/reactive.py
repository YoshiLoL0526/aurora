"""Reactividad de grano fino: componentes memorizados y regiones de la vista.

**Componentes.** Un `@component` no se vuelve a construir si sus argumentos son
los mismos y no cambió ninguno de los `Signal` que leyó al construirse. En ese
caso devuelve el mismo `Element`, que además recuerda su serialización: Python
no vuelve a recorrer esa rama, y el núcleo reconoce el dict y reutiliza el nodo
ya parseado. Si solo cambió lo que leen sus textos o propiedades con lambda, se
reutiliza el `Element` y se vuelve a serializar.

    @component
    def fila(tarea: Tarea, seleccionada: bool):
        return row(key=f"tarea-{tarea.id}", bg="$surface" if seleccionada else None)[...]

Las dependencias de un componente anidado cuentan también para el que lo
contiene: si cambia el de dentro, se reconstruye el de fuera.

**Regiones.** Las funciones dentro de la vista (el contenido de
`text(lambda: ...)`, una propiedad `bg=lambda: ...`, un hijo
`column()[lambda: [...]]`) se evalúan al serializar, y cada una anota los
`Signal` que lee. Si, sin un evento de por medio (ver `_core.build_partial`), lo
que cambió solo lo leen regiones (y no la función de la vista ni un componente
al construirse), la vista **no se vuelve a llamar**: se
reevalúan esas regiones, sus antepasados reciben un dict nuevo y todo lo demás
reutiliza el que ya tenía (marcado como memorizado para que el núcleo lo
comparta sin volver a leerlo). Ver `build_view`.

Cada reconstrucción es una sesión **de su dueño** (la `App`, una `Window`…): lo
memorizado se guarda por dueño, así dos ventanas que comparten un componente no
se pisan las memorizaciones al reconstruir la una a la otra. Al terminar la
sesión se olvidan las entradas que ese dueño no usó (componentes que ya no
están en su vista).
"""

from __future__ import annotations

import functools
import threading
import weakref
from collections.abc import Callable
from typing import Any, Generic, ParamSpec

from . import _flags
from .elements import _LAZY_CHILDREN, _MEMO, _VOLATILE, Element, _tracking
from .signal import Frame, Signal, current_frame, frames, fresh

P = ParamSpec("P")

# Pila de sesiones de construcción `(dueño, sesión)`. Por hilo: construir la
# vista es cosa del hilo de su runtime, pero un `Signal` se puede leer desde
# cualquiera (como `frames()`).
_local = threading.local()
_next_session = 0
_components: weakref.WeakSet[Component[...]] = weakref.WeakSet()


def _sessions() -> list[tuple[Any, int]]:
    stack = getattr(_local, "sessions", None)
    if stack is None:
        stack = _local.sessions = []
    return stack


def _current_session() -> tuple[Any, int]:
    stack = _sessions()
    return stack[-1] if stack else (None, 0)


class Entry:
    """Resultado memorizado de una llamada a un componente."""

    __slots__ = ("children", "deps", "element", "generation", "spec", "spec_children", "spec_deps", "theme")

    def __init__(self, element: Element, frame: Frame) -> None:
        self.element = element
        # Lo que leyó al construirse: si cambia, hay que volver a llamarlo.
        self.deps: dict[Signal[Any], int] = frame.deps
        # Componentes anidados: siguen vivos mientras este se reutilice.
        self.children: list[Entry] = frame.children
        self.generation = _current_session()[1]
        self.spec: dict[str, Any] | None = None
        self.theme: Any = None
        # Lo que leyó al serializarse (lambdas de textos, propiedades e hijos):
        # si cambia, basta con volver a serializar el mismo `Element`.
        self.spec_deps: dict[Signal[Any], int] = {}
        self.spec_children: list[Entry] = []

    def touch(self) -> None:
        self.generation = _current_session()[1]
        for child in self.children:
            child.touch()
        for child in self.spec_children:
            child.touch()

    def spec_for(self, theme: Any, build: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        """Serialización memorizada de la raíz del componente (la llama `Element.to_spec`)."""
        if self.spec is not None and self.theme is theme and fresh(self.spec_deps):
            report_spec(self)
            return self.spec
        frame = Frame()
        stack = frames()
        stack.append(frame)
        # Dentro se serializa sin seguimiento: el componente es una sola región.
        tracker = _tracking.tracker
        _tracking.tracker = None
        try:
            spec = build()
        finally:
            _tracking.tracker = tracker
            stack.pop()
        self.spec_deps = frame.deps
        self.spec_children = frame.children
        # El núcleo cachea el nodo parseado de los dicts marcados (por identidad).
        spec["memo"] = True
        self.spec, self.theme = spec, theme
        report_spec(self)
        return spec


def report(entry: Entry) -> None:
    """Hace que lo que se está construyendo dependa de `entry` (de lo que leyó al construirse)."""
    frame = current_frame()
    if frame is not None:
        for signal, version in entry.deps.items():
            frame.deps.setdefault(signal, version)
        frame.children.append(entry)


def report_spec(entry: Entry) -> None:
    """Hace que lo que se está serializando dependa de lo que `entry` leyó al serializarse."""
    frame = current_frame()
    if frame is not None:
        for signal, version in entry.spec_deps.items():
            frame.deps.setdefault(signal, version)
        frame.children.append(entry)


class Component(Generic[P]):
    def __init__(self, fn: Callable[P, Element]) -> None:
        self.fn = fn
        self.name: str = getattr(fn, "__name__", repr(fn))
        # Clave: `(dueño, argumentos, kwargs)`; ver `__call__`.
        self.cache: dict[tuple[Any, ...], Entry] = {}
        functools.update_wrapper(self, fn)
        _components.add(self)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Element:
        owner, _ = _current_session()
        try:
            key: tuple[Any, ...] | None = (owner, args, tuple(sorted(kwargs.items())))
            entry = self.cache.get(key)
        except TypeError:  # argumentos (o dueño) no hashables: no se memoriza
            key, entry = None, None
        if entry is not None and fresh(entry.deps):
            entry.touch()
            report(entry)
            return entry.element

        frame = Frame()
        stack = frames()
        stack.append(frame)
        try:
            element = self.fn(*args, **kwargs)
        finally:
            stack.pop()
        if not isinstance(element, Element):
            raise TypeError(f"el componente {self.name} debe devolver un Element")
        entry = Entry(element, frame)
        # Si devuelve tal cual el resultado de otro componente, la serialización
        # memorizada ya es la de ese otro (y sus dependencias ya están en `frame`).
        if element._memo is None:
            element._memo = entry
            element._dyn |= _MEMO
        if key is not None:
            self.cache[key] = entry
        report(entry)
        return element

    def __repr__(self) -> str:
        return f"<component {self.name}>"


def component(fn: Callable[P, Element]) -> Component[P]:
    """Memoriza un componente: solo se reconstruye si cambian sus argumentos
    (comparados con `==`; deben ser hashables) o algún `Signal` que haya leído.

    Un componente debe depender solo de sus argumentos y de `Signal`: si lee
    estado mutable normal (una lista global, un atributo), no se enterará de sus
    cambios. Las lambdas creadas en cada llamada (`on_click=lambda: ...`) no se
    pasan como argumento: son distintas cada vez e impedirían memorizarlo.
    """
    return Component(fn)


def current_owner() -> Any:
    """El dueño de la construcción en curso (una `App` o una `Window`), o `None` fuera de ella."""
    owner, _ = _current_session()
    return owner


def begin_build(owner: Any) -> None:
    """Abre una sesión de construcción para `owner` (una `App`, una `Window`, un `Pilot`)."""
    global _next_session
    _next_session += 1
    _sessions().append((owner, _next_session))


def end_build() -> None:
    """Cierra la sesión y olvida lo que su dueño no usó en esta reconstrucción."""
    stack = _sessions()
    owner, session = stack.pop() if stack else (None, 0)
    for comp in list(_components):
        comp.cache = {
            key: entry
            for key, entry in comp.cache.items()
            if key[0] is not owner or entry.generation == session
        }


# --- Regiones de la vista ---------------------------------------------------


class Region:
    """Un elemento cuya serialización leyó `Signal` (o que se rehace siempre)."""

    __slots__ = ("chain", "deps", "element", "entries")

    def __init__(self, element: Element, frame: Frame, chain: tuple[Element, ...]) -> None:
        self.element = element
        self.deps = frame.deps
        # Componentes creados al evaluarla (en un hijo calculado).
        self.entries: list[Entry] = frame.children
        # Sus antepasados, desde la raíz: los que necesitan un dict nuevo si se rehace.
        self.chain = chain


class Tracker:
    """Serialización que anota las regiones. Con `marked` (id → `True` si hay que
    rehacer el elemento, `False` si solo cambian sus hijos) es incremental: lo
    que no está marcado devuelve el dict de la serialización anterior."""

    __slots__ = ("marked", "regions", "stack", "theme")

    def __init__(self, theme: Any, regions: list[Region], marked: dict[int, bool] | None = None) -> None:
        self.theme = theme
        self.regions = regions
        self.marked = marked
        self.stack: list[Element] = []

    def run(self, root: Element) -> dict[str, Any]:
        previous = _tracking.tracker
        _tracking.tracker = self
        try:
            return self.spec(root)
        finally:
            _tracking.tracker = previous

    def children(self, parent: Element, kids: list[Element]) -> list[dict[str, Any]]:
        """Serializa los hijos de `parent` (lo llama `Element._children_spec`)."""
        stack = self.stack
        stack.append(parent)
        try:
            if self.marked is not None:
                return [self.spec(c) for c in kids]
            # Serialización completa: lo habitual es un hijo sin nada dinámico, que se
            # serializa sin pasar por `spec` (es el camino caliente de una vista grande).
            theme = self.theme
            out = []
            for c in kids:
                if c._dyn:
                    out.append(self.spec(c))
                else:
                    spec = c._spec = c._to_spec(theme)
                    out.append(spec)
            return out
        finally:
            stack.pop()

    def spec(self, e: Element) -> dict[str, Any]:
        marked = self.marked
        if marked is not None:
            redo = marked.get(id(e))
            cached = e._spec
            if cached is not None and redo is not True:
                if redo is None:
                    # Sin cambios: el mismo dict, que el núcleo ya puede compartir.
                    cached["memo"] = True
                    return cached
                # Cambia algo por debajo: dict nuevo con los mismos datos propios.
                spec = dict(cached)
                kids = e._kids if e._dyn & _LAZY_CHILDREN and e._kids is not None else e.children
                spec["children"] = self.children(e, kids)
                e._spec = spec
                return spec
        if not e._dyn:
            spec = e.to_spec(self.theme)
            e._spec = spec
            return spec
        frame = Frame()
        stack = frames()
        stack.append(frame)
        try:
            spec = e.to_spec(self.theme)
        finally:
            stack.pop()
        if frame.deps or e._dyn & _VOLATILE:
            self.regions.append(Region(e, frame, tuple(self.stack)))
        e._spec = spec
        return spec


class View:
    """Lo que queda de la última reconstrucción completa de la vista de un dueño."""

    __slots__ = ("deps", "entries", "key", "regions", "root", "theme")

    def __init__(self, key: Any, theme: Any, root: Element, frame: Frame, regions: list[Region]) -> None:
        self.key = key
        self.theme = theme
        self.root = root
        # Lo que leyó la función de la vista (y sus componentes) al construirse.
        self.deps = frame.deps
        self.entries: list[Entry] = frame.children
        self.regions = regions

    def update(self, stale: list[Region]) -> dict[str, Any]:
        """Rehace las regiones `stale` (y las volátiles) y reutiliza el resto del árbol."""
        redo = stale + [r for r in self.regions if r.element._dyn & _VOLATILE and fresh(r.deps)]
        ids = {id(r.element) for r in redo}
        # Lo que dieron los hijos calculados que se rehacen se sustituye entero:
        # sus regiones se vuelven a descubrir al serializarlo.
        outputs: set[int] = set()
        for r in redo:
            e = r.element
            if e._dyn & _LAZY_CHILDREN and e._kids is not None:
                static = {id(c) for c in e.children}
                outputs.update(id(k) for k in e._kids if id(k) not in static)
        kept = [
            r
            for r in self.regions
            if id(r.element) not in ids
            and not (outputs and (id(r.element) in outputs or any(id(a) in outputs for a in r.chain)))
        ]
        marked: dict[int, bool] = {}
        for r in redo:
            for ancestor in r.chain:
                marked.setdefault(id(ancestor), False)
        for i in ids:
            marked[i] = True
        # Los componentes de lo que se reutiliza siguen vivos.
        for entry in self.entries:
            entry.touch()
        for r in kept:
            for entry in r.entries:
                entry.touch()
        tracker = Tracker(self.theme, kept, marked)
        spec = tracker.run(self.root)
        self.regions = tracker.regions
        return spec


def partial_enabled() -> bool:
    """La reconstrucción parcial, salvo con `AURORA_PARTIAL=0` (u `off`, `false`, `no`)."""
    return _flags.enabled(None, "AURORA_PARTIAL", default=True)


def build_view(
    owner: Any,
    key: Any,
    view: Callable[[], Element],
    theme: Any,
    prepare: Callable[[Element], None],
    partial: bool = False,
) -> dict[str, Any]:
    """Serializa la vista de `owner` (dentro de su sesión, entre `begin_build` y `end_build`).

    Con `partial` (desde la última vez no corrió código de usuario por un
    evento, ver `_core.build_partial`), si solo cambiaron `Signal` que leen
    regiones, no se llama a `view`: se rehacen esas regiones sobre el árbol
    anterior. En cualquier otro caso (un manejador pudo cambiar estado normal
    de Python; cambió algo que leyó la vista o un componente al construirse,
    otra vista u otro tema, o ningún `Signal` que lea esta vista) se
    reconstruye entera, como siempre. `key` identifica la vista (`None`: no
    reutilizarla); `prepare` completa la raíz recién construida (el estilo
    por defecto).
    """
    # Se guarda en el propio dueño, no en un `WeakKeyDictionary`: lo guardado
    # llega hasta él (la vista, los componentes y sus claves) y nunca se soltaría.
    # Fuera mientras se reconstruye: si algo falla, la próxima vez es completa.
    state: View | None = getattr(owner, "_view_state", None)
    owner._view_state = None
    if (
        partial
        and state is not None
        and key is not None
        and state.key is key
        and state.theme is theme
        and fresh(state.deps)
        and partial_enabled()
    ):
        stale = [r for r in state.regions if not fresh(r.deps)]
        if stale:
            spec = state.update(stale)
            owner._view_state = state
            return spec
    frame = Frame()
    stack = frames()
    stack.append(frame)
    try:
        root = view()
    finally:
        stack.pop()
    prepare(root)
    tracker = Tracker(theme, [])
    spec = tracker.run(root)
    if key is not None and tracker.regions:
        # Sin regiones no hay nada que rehacer por partes: no se retiene el árbol.
        owner._view_state = View(key, theme, root, frame, tracker.regions)
    return spec
