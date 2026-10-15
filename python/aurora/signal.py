"""Estado reactivo.

MVP: cualquier cambio de un Signal marca la vista como sucia y se reconstruye
entera (barato: el árbol es pequeño y el layout/paint corren en Rust).
La API ya está pensada para el siguiente paso: dependencias de grano fino
que invaliden solo la rama afectada.
"""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Signal(Generic[T]):
    __slots__ = ("_value", "_subscribers")

    def __init__(self, value: T) -> None:
        self._value = value
        self._subscribers: list[Callable[[T], None]] = []

    def __call__(self) -> T:
        return self._value

    @property
    def value(self) -> T:
        return self._value

    def set(self, value: T) -> None:
        if value == self._value:
            return
        self._value = value
        for fn in tuple(self._subscribers):
            fn(value)

    def update(self, fn: Callable[[T], T]) -> None:
        self.set(fn(self._value))

    def subscribe(self, fn: Callable[[T], None]) -> Callable[[], None]:
        self._subscribers.append(fn)
        return lambda: self._subscribers.remove(fn)

    def __repr__(self) -> str:
        return f"Signal({self._value!r})"
