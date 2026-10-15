"""Primitivas declarativas.

Un `Element` es una descripción inmutable-en-la-práctica de un nodo. Los hijos se
añaden con corchetes, lo que deja leer la jerarquía como si fuera markup:

    column(gap=12)[
        text("Hola", size=24),
        row(gap=8)[button("OK"), button("Cancelar", variant="ghost")],
    ]
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Union

from .theme import Theme

Child = Union["Element", str, bool, None, Iterable["Child"]]
TextLike = str | Callable[[], Any]

# Alias cómodos para los props de texto más usados.
_ALIASES = {"size": "font_size", "weight": "font_weight", "family": "font_family"}


class Element:
    """Nodo de la vista.

    Los argumentos `on_<evento>` se guardan como manejadores (`handlers`) y el
    resto como propiedades de estilo.
    """

    __slots__ = ("children", "content", "handlers", "key", "kind", "style")

    def __init__(
        self,
        kind: str = "box",
        *,
        content: TextLike | None = None,
        key: str | None = None,
        **props: Any,
    ) -> None:
        self.kind = kind
        self.content = content
        self.key = key
        self.handlers: dict[str, Callable[..., Any]] = {
            k.removeprefix("on_"): v for k, v in props.items() if k.startswith("on_") and v is not None
        }
        self.style = {
            _ALIASES.get(k, k): v for k, v in props.items() if not k.startswith("on_") and v is not None
        }
        self.children: list[Element] = []

    @property
    def on_click(self) -> Callable[..., Any] | None:
        return self.handlers.get("click")

    def __getitem__(self, children: Child) -> Element:
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
            "handlers": self.handlers,
            "children": [c.to_spec(theme) for c in self.children],
        }

    def __repr__(self) -> str:
        return f"<{self.kind} {self.style} children={len(self.children)}>"


def _flatten(children: Child) -> Iterable[Element]:
    # None/False permiten condicionales en línea: `cond and elemento`.
    if children is None or isinstance(children, bool):
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
