"""Primitivas declarativas.

Un `Element` es una descripción inmutable-en-la-práctica de un nodo. Los hijos se
añaden con corchetes, lo que deja leer la jerarquía como si fuera markup:

    column(gap=12)[
        text("Hola", size=24),
        row(gap=8)[button("OK"), button("Cancelar", variant="ghost")],
    ]
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Literal, Union

from .theme import Theme

Child = Union["Element", str, bool, None, Iterable["Child"]]
TextLike = str | Callable[[], Any]

# Alias cómodos para los props de texto más usados.
_ALIASES = {"size": "font_size", "weight": "font_weight", "family": "font_family"}
# Texto libre que no se interpreta como token de tema aunque empiece por "$".
_LITERAL = {"placeholder", "src"}


class Element:
    """Nodo de la vista.

    Los argumentos `on_<evento>` se guardan como manejadores (`handlers`) y el
    resto como propiedades de estilo.
    """

    __slots__ = ("_memo", "children", "content", "handlers", "key", "kind", "style")

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
        # Un solo recorrido: crear elementos es lo más frecuente al construir la vista.
        handlers: dict[str, Callable[..., Any]] = {}
        style: dict[str, Any] = {}
        for k, v in props.items():
            if v is None:
                continue
            if k[:3] == "on_":
                handlers[k[3:]] = v
            else:
                style[_ALIASES.get(k, k)] = v
        self.handlers = handlers
        self.style = style
        self.children: list[Element] = []
        # Raíz de un `@component`: su `Entry` memoriza la serialización.
        self._memo: Any = None

    @property
    def on_click(self) -> Callable[..., Any] | None:
        return self.handlers.get("click")

    def __getitem__(self, children: Child) -> Element:
        self.children = list(_flatten(children))
        return self

    def to_spec(self, theme: Theme) -> dict[str, Any]:
        """Serializa a la forma que consume el núcleo Rust (resolviendo tokens y lambdas)."""
        if self._memo is not None:
            return self._memo.spec_for(theme, lambda: self._to_spec(theme))
        return self._to_spec(theme)

    def _to_spec(self, theme: Theme) -> dict[str, Any]:
        content = self.content() if callable(self.content) else self.content
        return {
            "kind": self.kind,
            "key": self.key,
            "text": None if content is None else str(content),
            "style": {k: _resolve(theme, k, v) for k, v in self.style.items()},
            "handlers": self.handlers,
            "children": [c.to_spec(theme) for c in self.children],
        }

    def __repr__(self) -> str:
        return f"<{self.kind} {self.style} children={len(self.children)}>"


def _resolve(theme: Theme, prop: str, value: Any) -> Any:
    # Solo una cadena "$..." o una tupla pueden contener tokens: el resto pasa sin llamar al tema.
    if prop in _LITERAL:
        return value
    if isinstance(value, str):
        return theme.resolve(value) if value[:1] == "$" else value
    if isinstance(value, tuple):
        return theme.resolve(value)
    return value


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


# Claves de estilo que fijan el tamaño: con una de ellas no hace falta un alto por defecto.
_SIZED = frozenset({"height", "grow", "min_height", "max_height"})


def _default_height(style: Mapping[str, Any], height: float = 200) -> dict[str, Any]:
    """`{"height": height}` si `style` no fija el tamaño (`height`, `grow`, `min_height`
    o `max_height`); vacío si lo fija. Es el alto por defecto de `canvas` y `chart`."""
    return {} if _SIZED & style.keys() else {"height": height}


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


Fit = Literal["contain", "cover", "fill", "none"]


def image(src: str | os.PathLike[str] | bytes, *, fit: Fit = "contain", **style: Any) -> Element:
    """Imagen de un archivo (PNG, JPEG, WebP, GIF, BMP, ICO o SVG) o de bytes en memoria.

    Sin `width` ni `height` ocupa su tamaño natural (sin pasar del ancho
    disponible); con uno de los dos, el otro sale de su proporción. `fit` decide
    cómo encaja si se fijan ambos. Se decodifica una vez y se reutiliza.
    """
    source = bytes(src) if isinstance(src, (bytes, bytearray, memoryview)) else os.fspath(src)
    return Element("image", src=source, fit=fit, **style)


def scroll(*, axis: Literal["x", "y", "both"] = "y", **style: Any) -> Element:
    """Contenedor desplazable: recorta su contenido y se desplaza con rueda, trackpad o barra.

    Apila sus hijos en el eje que se desplaza. Uno vertical sin `height` ni
    `max_height` ocupa el espacio libre (`grow=1`). Dale una `key` para conservar
    la posición aunque cambie de sitio en el árbol.
    """
    defaults: dict[str, Any] = {
        "direction": "row" if axis == "x" else "column",
        "scrollbar_color": "$muted",
    }
    if axis != "x" and "height" not in style and "max_height" not in style:
        defaults["grow"] = 1
    return Element("box", scroll=axis, **{**defaults, **style})
