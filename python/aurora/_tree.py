"""El árbol pintado de un frame, en texto o en datos, con avisos de layout (`aurora tree`).

Une el volcado de layout del `Pilot` (`layout()`: cajas, recortes y medidas del texto) con su árbol
de accesibilidad (`a11y_tree()`: roles, nombres y estados) en un único árbol de `Node`, pensado
para que un agente que solo lee texto entienda la interfaz y encuentre las keys que usar.

Los avisos (`warnings`) son los que se detectan de forma barata y fiable con esos datos; sus
límites están en `docs/reference.md` (§ «Comprobar desde la terminal»).
"""

from __future__ import annotations

import difflib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from ._core import Pilot

Rect = tuple[float, float, float, float]

# Holgura (px) antes de dar un texto por desbordado o un nodo por fuera de la ventana: el layout
# redondea y los párrafos se maquetan con medio píxel de margen.
SLACK = 1.0
# Largo máximo de un texto en la salida compacta.
TEXT_CHARS = 60
# Roles que no aportan nada en la salida compacta (se muestra el tipo de nodo).
_PLAIN_ROLES = {"generic", "window", "label", "", None}
_PATH = re.compile(r"\d+")


@dataclass(eq=False)
class Node:
    """Un nodo pintado: su caja, lo que dice a un lector de pantalla y sus hijos."""

    key: str
    kind: str  # box, text, input, image, canvas, chart o link
    rect: Rect
    visible: Rect | None  # lo que no recortan los scroll ni los overflow="hidden"
    explicit: bool  # la key la puso el código (no es una ruta del árbol)
    interactive: bool = False
    focusable: bool = False
    editable: bool = False
    scroll: str | None = None
    text: str | None = None
    role: str | None = None
    label: str | None = None
    value: str | None = None
    placeholder: str | None = None
    states: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    cut: bool = False
    text_size: tuple[float, float] | None = None
    content_size: tuple[float, float] | None = None
    children: list[Node] = field(default_factory=list)
    parent: Node | None = field(default=None, repr=False)

    def walk(self) -> Iterator[Node]:
        yield self
        for child in self.children:
            yield from child.walk()

    def name(self) -> str:
        """Lo que se lee del nodo: su nombre accesible o su texto."""
        return self.label or self.text or ""

    def contents(self) -> str:
        """Todo el texto del subárbol (textos, nombres y valores), separado por espacios."""
        parts: list[str] = []
        for n in self.walk():
            parts += dict.fromkeys(p for p in (n.text, n.label, n.value) if p)
        return " ".join(parts)

    def to_dict(self, depth: int | None = None) -> dict[str, Any]:
        d: dict[str, Any] = {
            "key": self.key,
            "kind": self.kind,
            "role": self.role,
            "explicit_key": self.explicit,
            "rect": list(self.rect),
            "visible": list(self.visible) if self.visible else None,
        }
        for name in ("text", "label", "value", "placeholder", "scroll"):
            value = getattr(self, name)
            if value is not None:
                d[name] = value
        d.update(
            interactive=self.interactive,
            focusable=self.focusable,
            editable=self.editable,
            states=self.states,
            actions=self.actions,
        )
        if self.text_size is not None:
            d["text_size"] = list(self.text_size)
            d["content_size"] = list(self.content_size or (0, 0))
        if depth is None or depth > 0:
            d["children"] = [c.to_dict(None if depth is None else depth - 1) for c in self.children]
        elif self.children:
            d["children_omitted"] = len(self.children)
        return d


@dataclass
class LayoutWarning:
    """Un aviso de layout sobre el nodo `key`. `code` es estable (para filtrar); `message`, para
    leerlo."""

    code: str
    key: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "key": self.key, "message": self.message}

    def __str__(self) -> str:
        return f"{self.code} #{self.key}: {self.message}"


@dataclass
class Snapshot:
    """El árbol de un frame: la raíz, los nodos por key y el tamaño de la ventana."""

    root: Node
    by_key: dict[str, Node]
    size: tuple[float, float]
    focused: str | None = None

    def find(self, key: str) -> Node | None:
        return self.by_key.get(key)

    def keys(self) -> list[str]:
        """Las keys explícitas (las que conviene usar), en orden de pintura."""
        return [k for k, n in self.by_key.items() if n.explicit]

    def suggest(self, key: str, n: int = 3) -> list[str]:
        """Keys parecidas a `key` (las explícitas primero)."""
        close = difflib.get_close_matches(key, self.keys(), n=n, cutoff=0.5)
        if not close:
            close = difflib.get_close_matches(key, list(self.by_key), n=n, cutoff=0.6)
        return close

    def missing(self, key: str) -> str:
        """Mensaje para una key que no está pintada, con sugerencias."""
        close = self.suggest(key)
        if close:
            hint = f" ¿Quisiste decir {' o '.join(repr(c) for c in close)}?"
        else:
            some = self.keys()[:8]
            hint = (
                f" Keys disponibles: {', '.join(some)}{'…' if len(self.keys()) > 8 else ''}" if some else ""
            )
        return f"no hay ningún nodo pintado con key {key!r}.{hint}"

    def warnings(self) -> list[LayoutWarning]:
        return warnings(self)


def snapshot(pilot: Pilot, size: tuple[float, float]) -> Snapshot:
    """El árbol del último frame de `pilot` (con una ventana de `size` píxeles lógicos)."""
    a11y = {n["key"]: n for n in pilot.a11y_tree() if n.get("key")}
    nodes: list[Node] = []
    for d in pilot.layout():
        parent = nodes[d["parent"]] if d["parent"] is not None else None
        key = d["key"]
        node = Node(
            key=key,
            kind=d["kind"],
            rect=tuple(d["rect"]),
            visible=tuple(d["visible"]) if d["visible"] else None,
            explicit=_explicit(key, parent),
            interactive=d["interactive"],
            focusable=d["focusable"],
            editable=d["editable"],
            scroll=d["scroll"],
            text=d["text"] if d["kind"] != "input" else None,
            cut=d["cut"],
            text_size=tuple(d["text_size"]) if "text_size" in d else None,
            content_size=tuple(d["content_size"]) if "content_size" in d else None,
            parent=parent,
        )
        if d.get("truncated"):
            node.states.append("truncated")
        info = a11y.get(key)
        if info is not None:
            _accessible(node, info)
        if node.visible is None:
            node.states.append("hidden")
        nodes.append(node)
        if parent is not None:
            parent.children.append(node)
    if not nodes:
        raise RuntimeError("el frame no pintó nada")
    by_key: dict[str, Node] = {}
    for n in nodes:
        by_key.setdefault(n.key, n)
    return Snapshot(nodes[0], by_key, size, pilot.focused)


def _explicit(key: str, parent: Node | None) -> bool:
    """Si la key no es la ruta que el núcleo pone a los nodos sin key (`padre/índice`)."""
    if parent is None:
        return not _PATH.fullmatch(key)
    head, sep, tail = key.rpartition("/")
    return not (sep and head == parent.key and _PATH.fullmatch(tail))


def _accessible(node: Node, info: dict[str, Any]) -> None:
    node.role = info.get("role")
    node.label = info.get("label") or None
    node.value = info.get("value") or None
    number = info.get("numeric_value")
    if node.value is None and number is not None:
        node.value = f"{number:g}"  # un deslizador o una barra de progreso
    node.placeholder = info.get("placeholder") or None
    node.actions = list(info.get("actions") or [])
    if info.get("focused"):
        node.states.append("focused")
    checked = info.get("checked")
    if checked is not None:
        node.states.append("checked" if checked else "unchecked")
    if info.get("selected"):
        node.states.append("selected")
    expanded = info.get("expanded")
    if expanded is not None:
        node.states.append("expanded" if expanded else "collapsed")
    if info.get("modal"):
        node.states.append("modal")


# ---------------------------------------------------------------------------
# Avisos


def warnings(snap: Snapshot) -> list[LayoutWarning]:
    """Avisos de layout del frame: texto que no cabe o queda recortado, controles de tamaño 0 o
    fuera de la ventana y controles sin nombre accesible."""
    out: list[LayoutWarning] = []
    width, height = snap.size
    for n in snap.root.walk():
        if n.kind == "text" and n.text_size and n.content_size:
            (tw, th), (cw, ch) = n.text_size, n.content_size
            if tw > cw + SLACK or th > ch + SLACK:
                out.append(
                    LayoutWarning(
                        "text-overflow",
                        n.key,
                        f"{_quote(n.text)} no cabe en su caja: necesita {_px(tw)}x{_px(th)} y tiene "
                        f"{_px(cw)}x{_px(ch)}",
                    )
                )
            elif n.cut and n.visible is not None:
                out.append(
                    LayoutWarning(
                        "text-clipped",
                        n.key,
                        f'{_quote(n.text)} queda recortado por un contenedor con overflow="hidden"',
                    )
                )
            elif (spill := _spill(n)) is not None:
                out.append(
                    LayoutWarning(
                        "text-overflow",
                        n.key,
                        f"{_quote(n.text)} se sale de su contenedor #{spill.key}: mide {_px(n.rect[2])}x"
                        f"{_px(n.rect[3])} y el contenedor {_px(spill.rect[2])}x{_px(spill.rect[3])}",
                    )
                )
        if not (n.interactive or n.focusable) or n.kind == "link":
            continue
        _, _, w, h = n.rect
        what = _describe(n)
        if w < SLACK or h < SLACK:
            out.append(
                LayoutWarning("zero-size", n.key, f"{what} mide {_px(w)}x{_px(h)}: no se puede pulsar")
            )
            continue
        if n.visible is not None:
            vx, vy, vw, vh = n.visible
            outside = vx >= width or vy >= height or vx + vw <= 0 or vy + vh <= 0
            if outside:
                out.append(
                    LayoutWarning(
                        "offscreen",
                        n.key,
                        f"{what} está fuera de la ventana ({_box(n.rect)} en {_px(width)}x{_px(height)})",
                    )
                )
            elif vx < -SLACK or vy < -SLACK or vx + vw > width + SLACK or vy + vh > height + SLACK:
                out.append(
                    LayoutWarning(
                        "offscreen",
                        n.key,
                        f"{what} se sale de la ventana ({_box(n.rect)} en {_px(width)}x{_px(height)})",
                    )
                )
        # Solo los controles sin nada que los nombre: ni label, ni placeholder, ni texto dentro (un
        # icono). El valor no cuenta: «50» no dice qué ajusta un deslizador.
        named = n.placeholder or any(m.text or m.label for m in n.walk())
        if n.role is not None and {"click", "focus"} & set(n.actions) and not named:
            out.append(
                LayoutWarning(
                    "no-label", n.key, f'{what} no tiene nombre accesible ni texto: añade label="…"'
                )
            )
    return out


def _spill(n: Node) -> Node | None:
    """El contenedor del que se sale `n` (sin recortarlo), si se sale. Un `scroll` no cuenta: su
    contenido lo desborda a propósito."""
    parent = n.parent
    if parent is None or parent.scroll:
        return None
    x, y, w, h = n.rect
    px, py, pw, ph = parent.rect
    if x < px - SLACK or y < py - SLACK or x + w > px + pw + SLACK or y + h > py + ph + SLACK:
        return parent
    return None


def _describe(n: Node) -> str:
    role = n.kind if n.role in _PLAIN_ROLES or n.role is None else n.role
    return f"{role} #{n.key}"


def _quote(text: str | None) -> str:
    """El texto entre comillas dobles, en una línea y acortado."""
    text = (text or "").replace("\n", " ")
    short = text if len(text) <= TEXT_CHARS else text[: TEXT_CHARS - 1] + "…"
    return json.dumps(short, ensure_ascii=False)


def _px(v: float) -> str:
    return str(round(v)) if abs(v - round(v)) < 0.05 else f"{v:.1f}"


def _box(r: Rect) -> str:
    x, y, w, h = r
    return f"{_px(x)},{_px(y)} {_px(w)}x{_px(h)}"


# ---------------------------------------------------------------------------
# Salida compacta


def _shown(n: Node) -> bool:
    """Si el nodo merece línea propia en la salida compacta. Los contenedores anónimos (sin key,
    sin rol, sin interacción) se omiten y sus hijos suben un nivel."""
    if n.parent is None or n.explicit or n.interactive or n.focusable or n.scroll:
        return True
    if n.kind != "box":
        # Un texto que repite el nombre de su control (el texto de un botón) sobra.
        owner = n.parent
        while owner is not None and not owner.interactive and not owner.explicit:
            owner = owner.parent
        return not (n.kind == "text" and owner is not None and owner.label and n.text == owner.label)
    return n.role not in _PLAIN_ROLES


def line(n: Node) -> str:
    """Una línea: `rol "nombre" #key = "valor" @x,y anchoxalto [estados]`."""
    role = n.kind if n.role in _PLAIN_ROLES or n.role is None else n.role
    parts = [role]
    name = n.name()
    if name:
        parts.append(_quote(name))
    elif n.placeholder:
        parts.append(f"placeholder={_quote(n.placeholder)}")
    if n.explicit or n.interactive or n.focusable or n.parent is None:
        parts.append(f"#{n.key}")
    if n.value is not None and n.value != name:
        parts.append(f"= {_quote(n.value)}")
    if n.scroll:
        parts.append(f"scroll={n.scroll}")
    parts.append(f"@{_box(n.rect)}")
    if n.states:
        parts.append(f"[{' '.join(n.states)}]")
    return " ".join(parts)


def format_tree(root: Node, *, depth: int | None = None) -> str:
    """El subárbol de `root` en texto indentado (dos espacios por nivel), hasta `depth` niveles
    mostrados por debajo de `root` (`None`: todos)."""
    lines: list[str] = []

    def visit(n: Node, level: int) -> None:
        shown = n is root or _shown(n)
        if shown:
            if depth is not None and level > depth:
                return
            lines.append(f"{'  ' * level}{line(n)}")
        below = level + 1 if shown else level
        if shown and depth is not None and below > depth and n.children:
            hidden = sum(1 for c in n.walk() if c is not n and _shown(c))
            if hidden:
                lines.append(f"{'  ' * below}… ({hidden} nodos más; sube --depth)")
            return
        for child in n.children:
            visit(child, below)

    visit(root, 0)
    return "\n".join(lines)


def format_warnings(items: list[LayoutWarning]) -> str:
    if not items:
        return "Sin avisos de layout."
    head = f"{len(items)} aviso{'s' if len(items) != 1 else ''} de layout:"
    return "\n".join([head, *(f"- {w}" for w in items)])
