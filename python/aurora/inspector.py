"""Inspector visual del árbol y profiler de frames.

Con el inspector activado (`App(view, inspector=True)` o la variable de entorno
`AURORA_INSPECTOR=1`), F12 acopla un panel a la derecha de la ventana:

- **Árbol**: los nodos de la vista con su tipo y su key. Un clic elige uno y
  muestra su caja, su estilo, su texto y sus eventos; el nodo elegido se
  resalta sobre la interfaz.
- **Modo selección** (Ctrl+Mayús+C o el botón ⌖): pasar el ratón por la
  interfaz resalta el nodo que hay debajo, con su padding, y un clic lo elige
  sin llegar a la app. Escape sale del modo.
- **Frames**: el coste de los últimos frames por fases (Python, parse, estilo,
  layout, draw y pintura) frente al presupuesto de 60 fps.

El panel se construye con las mismas primitivas que cualquier app; el núcleo
pone el resto (modo selección, resaltado e historial de frames) y se lo presta
a la vista mientras se construye (`_core.inspection()`).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from . import _core
from .canvas import Canvas, canvas
from .components import divider, tabs, virtual_list
from .elements import Element, box, column, row, scroll, spacer, text
from .signal import Signal
from .theme import MIDNIGHT, Theme

PANEL_KEY = "aurora:inspector"
TREE_KEY = "aurora:inspector-tree"
WIDTH = 380
ROW_HEIGHT = 22
INDENT = 12

# Presupuesto de un frame a 60 fps (ms).
BUDGET = 1000 / 60

# Fases del frame: clave en las estadísticas, nombre y color en la gráfica.
PHASES: Sequence[tuple[str, str, str]] = (
    ("build", "Python", "#A78BFA"),
    ("parse", "Parse", "#60A5FA"),
    ("style", "Estilo", "#22D3B6"),
    ("layout", "Layout", "#FBBF24"),
    ("draw", "Draw", "#F87171"),
    ("paint", "Pintura", "#34D399"),
)

# Tema propio del panel: se ve igual en apps claras, oscuras o con tema a medida.
THEME = Theme(
    colors={
        **MIDNIGHT.colors,
        "background": "#10131B",
        "surface": "#151925",
        "row_selected": "#2A2350",
        "key": "#C3B5FF",
        "string": "#86EFAC",
        "number": "#FCD34D",
    },
    radius=MIDNIGHT.radius,
)


def enabled(flag: bool | None) -> bool:
    """`flag` si se indica; si no, la variable de entorno `AURORA_INSPECTOR`."""
    if flag is not None:
        return flag
    return os.environ.get("AURORA_INSPECTOR", "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(slots=True)
class Node:
    """Un nodo del árbol de la vista, aplanado para listarlo."""

    key: str
    depth: int
    spec: dict[str, Any]
    parent: int | None
    children: int


def outline(spec: dict[str, Any], key: str) -> list[Node]:
    """Aplana el árbol serializado en orden de documento.

    Las keys siguen la misma regla que el núcleo: la explícita o la del padre
    seguida de la posición (`"0/1/2"`).
    """
    nodes: list[Node] = []
    stack: list[tuple[dict[str, Any], str, int, int | None]] = [(spec, key, 0, None)]
    while stack:
        d, path, depth, parent = stack.pop()
        k = d.get("key") or path
        children = d.get("children") or []
        index = len(nodes)
        nodes.append(Node(k, depth, d, parent, len(children)))
        for i in range(len(children) - 1, -1, -1):
            stack.append((children[i], f"{k}/{i}", depth + 1, index))
    return nodes


def kind_of(d: dict[str, Any]) -> str:
    """Nombre legible del nodo: `row`, `column` y `scroll` en vez de `box`."""
    kind = d.get("kind", "box")
    style = d.get("style") or {}
    if kind == "box":
        if style.get("scroll"):
            return "scroll"
        return "row" if style.get("direction") == "row" else "column"
    return kind


def summary(d: dict[str, Any]) -> str:
    """Contenido corto de un nodo para su fila: el texto, la imagen…"""
    content = d.get("text")
    if content:
        content = " ".join(str(content).split())
        return f'"{content[:40]}…"' if len(content) > 40 else f'"{content}"'
    style = d.get("style") or {}
    src = style.get("src")
    if isinstance(src, str):
        return os.path.basename(src)
    return ""


def format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, tuple | list):
        return "(" + ", ".join(format_value(v) for v in value) + ")"
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if callable(value):
        return "ƒ"
    text_value = str(value)
    return text_value if len(text_value) <= 60 else text_value[:59] + "…"


def is_color(value: Any) -> bool:
    return isinstance(value, str) and value[:1] == "#" and len(value) in (4, 5, 7, 9)


class Inspector:
    """Estado del panel que no guarda el núcleo: pestaña y ramas plegadas."""

    def __init__(self) -> None:
        self.tab: Signal[str] = Signal("tree")
        self.collapsed: set[str] = set()
        # Última selección vista: al cambiar, se despliegan sus ancestros.
        self._revealed: str | None = None

    def dock(self, spec: dict[str, Any], info: dict[str, Any], font_family: str) -> dict[str, Any]:
        """Acopla el panel a la derecha de la vista ya serializada."""
        style = spec.get("style") or {}
        # Copia sin la marca de memoria: el dict original puede estar memorizado.
        user = {k: v for k, v in spec.items() if k != "memo"}
        user["style"] = {**style, "grow": 1, "shrink": 1, "min_width": 0}
        nodes = outline(user, "0/0")
        panel = self.panel(nodes, info).to_spec(THEME)
        panel["style"] = {**panel["style"], "font_family": font_family}
        separator = box(width=1, bg=THEME.colors["border"]).to_spec(THEME)
        return {
            "kind": "box",
            "key": None,
            "text": None,
            "style": {"direction": "row", "bg": style.get("bg")},
            "handlers": {},
            "children": [user, separator, panel],
        }

    # --- panel ---------------------------------------------------------------

    def panel(self, nodes: list[Node], info: dict[str, Any]) -> Element:
        pick = info["pick"]
        header = row(gap=6, padding=(10, 10, 6, 14), align="center")[
            text("Inspector", weight=700, size=14),
            spacer(),
            box(
                key="aurora:inspector-pick",
                padding=(4, 8),
                radius=6,
                bg="$row_selected" if pick else "#00000000",
                bg_hover="$surface_hover",
                tooltip="Elegir un nodo de la interfaz (Ctrl+Mayús+C)",
                on_click=lambda: _core.inspect_pick(not pick),
            )[text("⌖ Elegir", size=12, weight=600, color="$key" if pick else "$muted")],
            box(
                key="aurora:inspector-close",
                padding=(4, 8),
                radius=6,
                bg_hover="$surface_hover",
                tooltip="Cerrar (F12)",
                on_click=lambda: _core.inspect_open(False),
            )[text("✕", size=12, color="$muted")],
        ]
        body = self.tree(nodes, info) if self.tab() == "tree" else self.frames(info["frames"])
        return column(key=PANEL_KEY, width=WIDTH, shrink=0, bg="$surface", color="$text", font_size=12)[
            header,
            tabs(
                [("tree", "Árbol"), ("frames", "Frames")],
                self.tab,
                key="aurora:inspector-tabs",
                padding=(0, 6),
            ),
            body,
        ]

    # --- árbol ---------------------------------------------------------------

    def tree(self, nodes: list[Node], info: dict[str, Any]) -> Element:
        selected: str | None = info["selected"]
        by_key = {n.key: i for i, n in enumerate(nodes)}
        reveal = selected != self._revealed
        if reveal:
            self._revealed = selected
            i = by_key.get(selected) if selected is not None else None
            parent = nodes[i].parent if i is not None else None
            while parent is not None:
                self.collapsed.discard(nodes[parent].key)
                parent = nodes[parent].parent
        visible = self.visible(nodes)
        if reveal:
            row_index = next((i for i, n in enumerate(visible) if n.key == selected), None)
            if row_index is not None:
                top = row_index * ROW_HEIGHT
                _core.inspect_reveal(TREE_KEY, top - 2 * ROW_HEIGHT, top + 3 * ROW_HEIGHT)

        def item(i: int) -> Element:
            return self.row(visible[i], selected)

        current = nodes[by_key[selected]] if selected in by_key else None
        return column(grow=1, min_height=0)[
            virtual_list(len(visible), item, item_height=ROW_HEIGHT, key=TREE_KEY, min_height=0),
            divider(color="$border"),
            self.details(current, info["rect"]),
        ]

    def visible(self, nodes: list[Node]) -> list[Node]:
        """Los nodos que no están dentro de una rama plegada."""
        out: list[Node] = []
        hidden_below: int | None = None
        for n in nodes:
            if hidden_below is not None:
                if n.depth > hidden_below:
                    continue
                hidden_below = None
            out.append(n)
            if n.children and n.key in self.collapsed:
                hidden_below = n.depth
        return out

    def toggle(self, key: str) -> None:
        if key in self.collapsed:
            self.collapsed.discard(key)
        else:
            self.collapsed.add(key)

    def row(self, n: Node, selected: str | None) -> Element:
        d = n.spec
        is_selected = n.key == selected
        chevron: Element = box(width=14)
        if n.children:
            chevron = box(width=14, align="center", on_click=lambda: self.toggle(n.key), focusable=False)[
                text("▸" if n.key in self.collapsed else "▾", color="$muted", size=11)
            ]
        explicit = bool(d.get("key"))
        return row(
            grow=1,
            align="center",
            gap=6,
            padding=(0, 8, 0, 6 + n.depth * INDENT),
            bg="$row_selected" if is_selected else "#00000000",
            bg_hover="$row_selected" if is_selected else "$surface_hover",
            on_click=lambda: _core.inspect_select(n.key),
            focusable=False,
        )[
            chevron,
            text(kind_of(d), weight=600, color="$text" if is_selected else "#B9C0D4"),
            explicit and text(n.key, color="$key", max_lines=1),
            text(summary(d), color="$muted", max_lines=1, shrink=1),
        ]

    def details(self, n: Node | None, rect: tuple[float, float, float, float] | None) -> Element:
        if n is None:
            return column(padding=14, height=240, shrink=0)[
                text("Elige un nodo en el árbol o con ⌖ sobre la interfaz.", color="$muted"),
            ]
        d = n.spec
        style = d.get("style") or {}
        handlers = sorted(d.get("handlers") or {})
        box_text = (
            f"x {rect[0]:g}  y {rect[1]:g}   {rect[2]:g} × {rect[3]:g}"
            if rect is not None
            else "no se pintó (fuera de la vista o recortado)"
        )
        rows: list[Element] = [
            row(gap=6, align="center")[
                text(kind_of(d), weight=700, size=13),
                text(n.key, color="$key", max_lines=1, shrink=1),
            ],
            self.section("Caja", [text(box_text, color="$muted" if rect is None else "$text")]),
        ]
        content = d.get("text")
        if content is not None:
            rows.append(self.section("Texto", [text(str(content), color="$string", max_lines=4)]))
        if style:
            rows.append(self.section("Estilo", [self.prop(k, v) for k, v in style.items()]))
        if handlers:
            rows.append(
                self.section("Eventos", [text(", ".join(f"on_{h}" for h in handlers), color="$number")])
            )
        if n.children:
            noun = "hijo" if n.children == 1 else "hijos"
            rows.append(text(f"{n.children} {noun}", color="$muted"))
        return scroll(key="aurora:inspector-details", height=240, shrink=0, padding=(10, 14), gap=10)[rows]

    def section(self, title: str, content: list[Element]) -> Element:
        return column(gap=4)[
            text(title.upper(), size=10, weight=700, color="$muted", letter_spacing=0.6), content
        ]

    def prop(self, name: str, value: Any) -> Element:
        swatch = is_color(value) and box(
            width=10, height=10, radius=2, bg=value, border_width=1, border_color="$border"
        )
        color = "$number" if isinstance(value, int | float) and not isinstance(value, bool) else "$string"
        return row(gap=8, align="center")[
            text(name, color="$muted", width=118, max_lines=1),
            swatch,
            text(format_value(value), color=color, max_lines=1, shrink=1),
        ]

    # --- frames --------------------------------------------------------------

    def frames(self, frames: list[dict[str, Any]]) -> Element:
        if not frames:
            return column(padding=14)[text("Aún no hay frames.", color="$muted")]
        totals = [f["total"] for f in frames]
        last = frames[-1]
        ordered = sorted(totals)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        rebuilds = sum(1 for f in frames if f["rebuilt"])
        slow = sum(1 for t in totals if t > BUDGET)

        def figure(label: str, value: float) -> Element:
            tone = "$danger" if value > BUDGET else "$text"
            return column(gap=2, grow=1)[
                text(label, size=10, weight=700, color="$muted", letter_spacing=0.6),
                text(f"{value:.2f} ms", size=15, weight=700, color=tone),
            ]

        def draw(c: Canvas) -> None:
            graph(c, frames)

        breakdown = [
            row(gap=8, align="center")[
                box(width=8, height=8, radius=2, bg=color),
                text(name, grow=1),
                text(f"{last[phase]:.2f}", width=56, text_align="right"),
                text(f"{sum(f[phase] for f in frames) / len(frames):.2f}", width=56, text_align="right"),
                text(f"{max(f[phase] for f in frames):.2f}", width=56, text_align="right", color="$muted"),
            ]
            for phase, name, color in PHASES
        ]
        damage = last["damage"]
        repaint = f"{damage[2]:g} × {damage[3]:g} en ({damage[0]:g}, {damage[1]:g})" if damage else "nada"
        facts = [
            ("Nodos", f"{last['nodes']}"),
            ("Reconstruyó la vista", "sí" if last["rebuilt"] else "no"),
            ("Layout", "reutilizado" if last["layout_cached"] else "recalculado"),
            ("Zona repintada", repaint),
        ]
        return scroll(key="aurora:inspector-frames", padding=(12, 14), gap=14)[
            row(gap=8)[
                figure("ÚLTIMO", last["total"]),
                figure("MEDIA", sum(totals) / len(totals)),
                figure("P95", p95),
                figure("MÁX.", ordered[-1]),
            ],
            canvas(draw, key="aurora:inspector-graph", height=130, radius=6, bg="$background"),
            text(
                f"{len(frames)} frames · {rebuilds} reconstruyeron la vista · {slow} por encima de 16,7 ms",
                color="$muted",
                size=11,
            ),
            column(gap=6)[
                row(gap=8)[
                    box(width=8),
                    text("FASE (ms)", grow=1, size=10, weight=700, color="$muted"),
                    text("ÚLTIMO", width=56, text_align="right", size=10, weight=700, color="$muted"),
                    text("MEDIA", width=56, text_align="right", size=10, weight=700, color="$muted"),
                    text("MÁX.", width=56, text_align="right", size=10, weight=700, color="$muted"),
                ],
                breakdown,
            ],
            column(gap=4)[
                [
                    row(gap=8)[text(label, color="$muted", width=150), text(value, shrink=1, max_lines=1)]
                    for label, value in facts
                ]
            ],
        ]


def graph(c: Canvas, frames: list[dict[str, Any]]) -> None:
    """Barras apiladas por fase de cada frame, con la línea de los 60 fps."""
    pad_top, pad_bottom = 14.0, 4.0
    h = max(1.0, c.height - pad_top - pad_bottom)
    peak = max(f["total"] for f in frames)
    top = max(BUDGET * 1.5, peak * 1.1)
    slot = c.width / max(len(frames), 60)
    width = max(1.0, slot - 1.0)
    x = c.width - slot * len(frames)
    for f in frames:
        y = pad_top + h
        for phase, _, color in PHASES:
            v = f[phase] / top * h
            if v > 0.05:
                c.rect(x, y - v, width, v, fill=color)
                y -= v
        x += slot
    budget = pad_top + h - BUDGET / top * h
    c.line(0, budget, c.width, budget, stroke="#F8717199", dash=(4, 3))
    c.text(
        c.width - 6, budget - 2, "16,7 ms · 60 fps", color="$muted", size=10, align="right", baseline="bottom"
    )
    c.text(6, 2, f"{top:.1f} ms", color="$muted", size=10)
