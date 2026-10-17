"""Componentes memorizados: reactividad de grano fino.

`view()` se llama entera tras cada cambio, pero un `@component` no se vuelve a
construir si sus argumentos son los mismos y no cambió ninguno de los `Signal`
que leyó (al construirse o al resolver sus textos). En ese caso devuelve el mismo
`Element`, que además recuerda su serialización: Python no vuelve a recorrer esa
rama, y el núcleo reconoce el dict y reutiliza el nodo ya parseado.

    @component
    def fila(tarea: Tarea, seleccionada: bool):
        return row(key=f"tarea-{tarea.id}", bg="$surface" if seleccionada else None)[...]

Las dependencias de un componente anidado cuentan también para el que lo
contiene: si cambia el de dentro, se reconstruye el de fuera.

Cada reconstrucción es una sesión **de su dueño** (la `App`, una `Window`, un
`Pilot`…): lo memorizado se guarda por dueño, así dos ventanas que comparten un
componente no se pisan las memorizaciones al reconstruir la una a la otra. Al
terminar la sesión se olvidan las entradas que ese dueño no usó (componentes
que ya no están en su vista).
"""

from __future__ import annotations

import functools
import threading
import weakref
from collections.abc import Callable
from typing import Any, Generic, ParamSpec

from .elements import Element
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

    __slots__ = ("children", "deps", "element", "generation", "spec", "theme")

    def __init__(self, element: Element, frame: Frame) -> None:
        self.element = element
        self.deps: dict[Signal[Any], int] = frame.deps
        # Componentes anidados: siguen vivos mientras este se reutilice.
        self.children: list[Entry] = frame.children
        self.generation = _current_session()[1]
        self.spec: dict[str, Any] | None = None
        self.theme: Any = None

    def touch(self) -> None:
        self.generation = _current_session()[1]
        for child in self.children:
            child.touch()

    def spec_for(self, theme: Any, build: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        """Serialización memorizada de la raíz del componente (la llama `Element.to_spec`)."""
        if self.spec is not None and self.theme is theme and fresh(self.deps):
            report(self)
            return self.spec
        frame = Frame()
        stack = frames()
        stack.append(frame)
        try:
            spec = build()
        finally:
            stack.pop()
        # Lo que se lee al serializar (textos con lambda) también es una dependencia.
        for signal, version in frame.deps.items():
            self.deps.setdefault(signal, version)
        self.children.extend(frame.children)
        # El núcleo cachea el nodo parseado de los dicts marcados (por identidad).
        spec["memo"] = True
        self.spec, self.theme = spec, theme
        report(self)
        return spec


def report(entry: Entry) -> None:
    """Hace que el componente que se está construyendo dependa de `entry`."""
    frame = current_frame()
    if frame is not None:
        for signal, version in entry.deps.items():
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
