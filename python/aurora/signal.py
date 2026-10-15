"""Estado reactivo.

Cualquier cambio de un Signal marca la vista como sucia y `view()` se vuelve a
llamar. Para no reconstruir lo que no cambió, cada `Signal` lleva una versión y
registra quién lo lee: mientras se construye un `@component`, sus lecturas se
anotan como dependencias, y el componente se reutiliza mientras ninguna cambie
(ver `reactive.py`).

`set` es seguro desde cualquier hilo o corrutina: despierta el bucle de eventos
para que la ventana se actualice sin esperar a un evento del usuario.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from . import _core

T = TypeVar("T")


class Frame:
    """Lo que lee un componente mientras se construye: los `Signal` (con la
    versión que vio) y las entradas de los componentes anidados."""

    __slots__ = ("children", "deps")

    def __init__(self) -> None:
        self.deps: dict[Signal[Any], int] = {}
        self.children: list[Any] = []


# Pila de componentes en construcción. Por hilo: construir la vista es cosa del
# hilo de la interfaz, pero un `Signal` se puede leer desde cualquiera.
_local = threading.local()


def frames() -> list[Frame]:
    stack = getattr(_local, "frames", None)
    if stack is None:
        stack = _local.frames = []
    return stack


def current_frame() -> Frame | None:
    stack = frames()
    return stack[-1] if stack else None


class Signal(Generic[T]):
    __slots__ = ("_subscribers", "_value", "_version")

    def __init__(self, value: T) -> None:
        self._value = value
        self._version = 0
        self._subscribers: list[Callable[[T], None]] = []

    def __call__(self) -> T:
        frame = current_frame()
        if frame is not None:
            # Se guarda la primera versión leída: si cambió durante la construcción,
            # el componente queda desactualizado y se reconstruye la próxima vez.
            frame.deps.setdefault(self, self._version)
        return self._value

    @property
    def value(self) -> T:
        return self()

    def set(self, value: T) -> None:
        if value == self._value:
            return
        self._value = value
        self._version += 1
        for fn in tuple(self._subscribers):
            fn(value)
        _core.wake()

    def update(self, fn: Callable[[T], T]) -> None:
        self.set(fn(self._value))

    def subscribe(self, fn: Callable[[T], None]) -> Callable[[], None]:
        self._subscribers.append(fn)
        return lambda: self._subscribers.remove(fn)

    def __repr__(self) -> str:
        return f"Signal({self._value!r})"


def fresh(deps: dict[Signal[Any], int]) -> bool:
    """`True` si ningún `Signal` cambió desde que se leyó."""
    return all(signal._version == version for signal, version in deps.items())
