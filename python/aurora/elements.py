"""Primitivas declarativas.

Un `Element` es una descripción inmutable-en-la-práctica de un nodo. Los hijos se
añaden con corchetes, lo que deja leer la jerarquía como si fuera markup:

    column(gap=12)[
        text("Hola", size=24),
        row(gap=8)[button("OK"), button("Cancelar", variant="ghost")],
    ]
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Union

from .theme import Theme

Child = Union["Element", str, None, Iterable["Child"]]
TextLike = Union[str, Callable[[], Any]]

# Alias cómodos para los props de texto más usados.
_ALIASES = {"size": "font_size", "weight": "font_weight", "family": "font_family"}


class Element:
    __slots__ = ("kind", "style", "content", "children", "on_click", "key")

    def __init__(
        self,
        kind: str = "box",
        *,
        content: TextLike | None = None,
        on_click: Callable[[], Any] | None = None,
        key: str | None = None,
        **style: Any,
    ) -> None:
        self.kind = kind
        self.content = content
        self.on_click = on_click
        self.key = key
        self.style = {_ALIASES.get(k, k): v for k, v in style.items() if v is not None}
        self.children: list[Element] = []

    def __getitem__(self, children: Child) -> "Element":
        self.children = list(_flatten(children))
        return self

    def to_spec(self, theme: Theme) -> dict[str, Any]:
        """Serializa a la forma que consume el núcleo Rust (resolviendo tokens y lambdas)."""
        content = self.content() if callable(self.content) else self.content
        return {
            "kind": self.kind,
            "key": self.key,
            "text": None if content is None else str(content),
            "style": {k: theme.resolve(v) for k, v in self.style.items()},
            "on_click": self.on_click,
            "children": [c.to_spec(theme) for c in self.children],
        }

    def __repr__(self) -> str:
        return f"<{self.kind} {self.style} children={len(self.children)}>"


def _flatten(children: Child) -> Iterable[Element]:
    if children is None:
        return
    if isinstance(children, Element):
        yield children
    elif isinstance(children, str):
        yield text(children)
    else:
        for child in children:
            yield from _flatten(child)


# --- Primitivas ------------------------------------------------------------

def box(**style: Any) -> Element:
    return Element("box", **style)


def column(**style: Any) -> Element:
    return Element("box", direction="column", **style)


def row(**style: Any) -> Element:
    return Element("box", direction="row", **style)


def text(content: TextLike, **style: Any) -> Element:
    return Element("text", content=content, **style)


def spacer() -> Element:
    return Element("box", grow=1)
