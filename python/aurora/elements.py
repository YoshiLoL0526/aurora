"""Primitivas declarativas.

Un `Element` es una descripción inmutable-en-la-práctica de un nodo. Los hijos se
añaden con corchetes, lo que deja leer la jerarquía como si fuera markup:

    column(gap=12)[
        text("Hola", size=24),
        row(gap=8)[button("OK"), button("Cancelar", variant="ghost")],
    ]

Las funciones son **regiones reactivas**: el contenido de `text(lambda: ...)`,
una propiedad (`bg=lambda: ...`) y un hijo (`column()[lambda: [...]]`) se
evalúan al serializar y anotan los `Signal` que leen. Si un cambio sin evento
(desde un hilo o `app.spawn`) solo afecta a regiones, la vista no se vuelve a
llamar: se reevalúan las regiones que leen
lo que cambió y el resto del árbol reutiliza su serialización (ver `reactive.py`).
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Union

from ._style import ENUMS, EVENT_NAMES, STYLE_NAMES, TOKEN_PROPS, invalid_value, unknown_prop
from .theme import KNOWN, Theme, ThemeTokenError, remember_origin

if TYPE_CHECKING:
    from typing import Unpack

    from ._style import Style
    from ._style_variants import ImageStyle

# `int` está por `n() and elemento`: un 0 no pinta nada (otro número es un error).
Child = Union["Element", str, bool, int, None, Callable[[], "Child"], Iterable["Child"]]
TextLike = str | Callable[[], Any]

# Texto libre que no se interpreta como token de tema aunque empiece por "$".
_LITERAL = {"placeholder", "src", "label", "alt", "description", "value", "role", "live"}

# Por qué un elemento no se serializa como uno fijo (`Element._dyn`, una máscara):
# alguna propiedad, algún hijo (`Dynamic`) o el contenido es una función, es la
# raíz de un `@component` o es `_volatile`. Con 0, `reactive.Tracker` lo
# serializa por el camino rápido.
_LAZY_STYLE = 1
_LAZY_CHILDREN = 2
_LAZY_CONTENT = 4
_MEMO = 8
_VOLATILE = 16


class _Tracking(threading.local):
    """Serialización con seguimiento en curso (la de `reactive.Tracker`), por hilo.
    `None` fuera de ella y dentro de un `@component`, que se memoriza entero."""

    tracker: Any = None


_tracking = _Tracking()


class Element:
    """Nodo de la vista.

    Los argumentos `on_<evento>` se guardan como manejadores (`handlers`) y el
    resto como propiedades de estilo.
    """

    __slots__ = ("_dyn", "_kids", "_memo", "_spec", "children", "content", "handlers", "key", "kind", "style")

    # Su serialización depende de algo que no avisa al cambiar (los datos de un
    # `chart`, que se pueden modificar en el sitio): se rehace en cada reconstrucción.
    _volatile: ClassVar[bool] = False

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
        dyn = _VOLATILE if self._volatile else 0
        if content is not None and callable(content):
            dyn |= _LAZY_CONTENT
        for k, v in props.items():
            # Una consulta dice a la vez si `k` es estilo, manejador o un error.
            name = STYLE_NAMES.get(k)
            if name is not None:
                if v is None:
                    continue
                style[name] = v
                if callable(v):
                    dyn |= _LAZY_STYLE
                elif name in ENUMS and v not in ENUMS[name]:
                    # Un valor reactivo (una función) lo valida el núcleo al leerlo.
                    raise invalid_value(kind, k, v)
                elif name in TOKEN_PROPS and type(v) is str and v[:1] == "$" and v[1:] not in KNOWN:
                    # Fallará al serializar: se apunta dónde se escribió para el error.
                    remember_origin(v)
                continue
            event = EVENT_NAMES.get(k)
            if event is None:
                raise unknown_prop(kind, k)
            if v is None:
                continue
            if event == "context_menu" and not callable(v):
                # Una lista describe el menú contextual; el núcleo la pide al
                # abrirlo, así que se envuelve en un callable.
                handlers["context_menu"] = lambda menu=v: menu
            else:
                handlers[event] = v
        self.handlers = handlers
        self.style = style
        self.children: list[Element] = []
        self._dyn = dyn
        # Raíz de un `@component`: su `Entry` memoriza la serialización.
        self._memo: Any = None
        # Última serialización y, con hijos calculados, los hijos que dieron.
        self._spec: dict[str, Any] | None = None
        self._kids: list[Element] | None = None

    @property
    def on_click(self) -> Callable[..., Any] | None:
        return self.handlers.get("click")

    def __getitem__(self, children: Child) -> Element:
        # Contar los `Dynamic` creados al aplanar cuesta menos que buscarlos entre los hijos.
        made = Dynamic.made
        self.children = list(_flatten(children))
        if Dynamic.made != made:
            self._dyn |= _LAZY_CHILDREN
        return self

    def to_spec(self, theme: Theme) -> dict[str, Any]:
        """Serializa a la forma que consume el núcleo Rust (resolviendo tokens y lambdas)."""
        if self._memo is not None:
            return self._memo.spec_for(theme, lambda: self._to_spec(theme))
        return self._to_spec(theme)

    def _to_spec(self, theme: Theme) -> dict[str, Any]:
        content = self.content() if callable(self.content) else self.content
        if self._dyn & _LAZY_STYLE:
            style = {k: _resolve(theme, k, v() if callable(v) else v) for k, v in self.style.items()}
        else:
            style = {k: _resolve(theme, k, v) for k, v in self.style.items()}
        return {
            "kind": self.kind,
            "key": self.key,
            "text": None if content is None else str(content),
            "style": style,
            "handlers": self.handlers,
            "children": self._children_spec(theme),
        }

    def _children_spec(self, theme: Theme) -> list[dict[str, Any]]:
        if self._dyn & _LAZY_CHILDREN:
            kids = self._kids = _expand(self.children)
        else:
            kids = self.children
            if not kids:  # una hoja: lo más frecuente
                return []
        tracker = _tracking.tracker
        if tracker is None:
            return [c.to_spec(theme) for c in kids]
        return tracker.children(self, kids)

    def __repr__(self) -> str:
        return f"<{self.kind} {self.style} children={len(self.children)}>"


class Dynamic(Element):
    """Hijo calculado (`column()[lambda: [...]]`): una función que devuelve
    hijos (lo mismo que admiten los corchetes) y se evalúa al serializar, en el
    sitio que ocupa entre sus hermanos. Es una región reactiva: se vuelve a
    evaluar cuando cambia un `Signal` que leyó."""

    __slots__ = ("fn",)

    # Cuántos se han creado (ver `Element.__getitem__`).
    made: ClassVar[int] = 0

    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__("box")
        self.fn = fn
        Dynamic.made += 1

    def _to_spec(self, theme: Theme) -> dict[str, Any]:
        # Serializado suelto (fuera de unos corchetes): una caja con lo que da.
        self.children = _expand([self])
        return super()._to_spec(theme)


def _expand(children: Iterable[Element]) -> list[Element]:
    """Los hijos, con los calculados (`Dynamic`) evaluados en su sitio."""
    out: list[Element] = []
    for child in children:
        if type(child) is Dynamic:
            out.extend(_expand(_flatten(child.fn())))
        else:
            out.append(child)
    return out


def _resolve(theme: Theme, prop: str, value: Any) -> Any:
    # Solo una cadena "$..." o una tupla pueden contener tokens: el resto pasa sin llamar al tema.
    if prop in _LITERAL:
        return value
    try:
        if isinstance(value, str):
            return theme.resolve(value) if value[:1] == "$" else value
        if isinstance(value, tuple):
            return theme.resolve(value)
    except ThemeTokenError as err:
        # El tema no sabe en qué propiedad estaba el token: se añade al mensaje, y
        # las sugerencias son del tipo que pide (radios en `radius`, colores en el resto).
        known = [*theme.radius] if prop == "radius" else [*theme.colors]
        raise ThemeTokenError(err.token, known, prop) from None
    return value


def _flatten(children: Child) -> Iterable[Element]:
    # None/False permiten condicionales en línea: `cond and elemento`. Con una
    # condición que es una cadena vacía o un 0 (`error() and text(error())`,
    # `n() and badge(...)`), `and` da ese valor: tampoco pinta nada.
    if children is None or isinstance(children, bool):
        return
    if isinstance(children, Element):
        yield children
    elif isinstance(children, str):
        if children:
            yield text(children)
    elif isinstance(children, (int, float)):
        if children:
            raise TypeError(f"un número no es un hijo: {children!r} (usa text(str(...)))")
    elif callable(children):
        yield Dynamic(children)
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


def box(**style: Unpack[Style]) -> Element:
    return Element("box", **style)


def column(**style: Unpack[Style]) -> Element:
    return Element("box", direction="column", **style)


def row(**style: Unpack[Style]) -> Element:
    return Element("box", direction="row", **style)


def text(content: TextLike, **style: Unpack[Style]) -> Element:
    return Element("text", content=content, **style)


def spacer() -> Element:
    return Element("box", grow=1)


Fit = Literal["contain", "cover", "fill", "none"]


def image(
    src: str | os.PathLike[str] | bytes, *, fit: Fit = "contain", **style: Unpack[ImageStyle]
) -> Element:
    """Imagen de un archivo (PNG, JPEG, WebP, GIF, BMP, ICO o SVG) o de bytes en memoria.

    Sin `width` ni `height` ocupa su tamaño natural (sin pasar del ancho
    disponible); con uno de los dos, el otro sale de su proporción. `fit` decide
    cómo encaja si se fijan ambos. Se decodifica una vez y se reutiliza.
    """
    source = bytes(src) if isinstance(src, (bytes, bytearray, memoryview)) else os.fspath(src)
    return Element("image", src=source, fit=fit, **style)


def scroll(*, axis: Literal["x", "y", "both"] = "y", **style: Unpack[Style]) -> Element:
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
