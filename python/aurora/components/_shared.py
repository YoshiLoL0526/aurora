"""Ayudantes internos compartidos por los componentes."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from typing import Any, TypeVar

from ..elements import Element, TextLike
from ..signal import Signal

T = TypeVar("T", bound=Hashable)
Options = Sequence[T] | Sequence[tuple[T, str]]


def _toggle(
    state: Signal[bool] | bool, on_change: Callable[[bool], Any] | None
) -> tuple[bool, Callable[[], None]]:
    """Valor actual y acción de alternarlo, para controles enlazados a un `Signal[bool]`."""
    current = state() if isinstance(state, Signal) else bool(state)

    def flip() -> None:
        value = not current
        if isinstance(state, Signal):
            state.set(value)
        if on_change is not None:
            on_change(value)

    return current, flip


def _items(options: Options) -> list[tuple[Any, str]]:
    return [o if isinstance(o, tuple) else (o, str(o)) for o in options]


def _has_autofocus(element: Element) -> bool:
    """Si algún nodo del subárbol pide el foco al aparecer (para no quitárselo)."""
    return bool(element.style.get("autofocus")) or any(_has_autofocus(c) for c in element.children)


_INPUT_STYLE: dict[str, Any] = dict(
    bg="$surface",
    border_width=1,
    border_color="$border",
    radius="$md",
    padding=(9, 12),
)


def _field(
    value: Signal[str] | TextLike,
    on_change: Callable[[str], Any] | None,
    on_submit: Callable[[str], Any] | None,
    key: str | None,
    style: dict[str, Any],
) -> Element:
    if isinstance(value, Signal):
        signal = value

        def change(text: str) -> None:
            signal.set(text)
            if on_change is not None:
                on_change(text)

        handler: Callable[[str], Any] | None = change
    else:
        handler = on_change
    return Element(
        "input",
        content=value,
        key=key,
        on_change=handler,
        on_submit=on_submit,
        **{**_INPUT_STYLE, **style},
    )
