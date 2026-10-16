"""Lienzo de dibujo inmediato.

`canvas(draw)` reserva una caja en el layout; `draw(c)` dibuja en ella con
comandos sueltos (rectángulos, líneas, trazados, texto…), como en un `<canvas>`
de HTML:

    def grafico(c: Canvas):
        c.clear("$surface")
        puntos = [(0, c.height), (c.width / 2, 20), (c.width, c.height / 2)]
        c.polyline(puntos, stroke="$primary", stroke_width=2)
        c.text(c.width - 8, 8, "máx.", align="right", color="$muted", size=12)

    canvas(grafico, height=180)

Los comandos no se ejecutan uno a uno: se acumulan en Python y cruzan al
núcleo en un solo lote, donde se graban en un `Picture` de Skia que se repinta
sin volver a Python (hover, scroll, animaciones de otros nodos).

`draw` se llama después del layout, cuando ya se sabe el tamaño (`c.width`,
`c.height`): al reconstruirse la vista y cuando el lienzo cambia de tamaño. Si
el `canvas` está dentro de un `@component` que no se reconstruye, `draw` solo
se repite si cambia el tamaño o algún `Signal` que haya leído.
"""

from __future__ import annotations

from array import array
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from itertools import chain
from typing import Any, Literal

from .elements import Element
from .signal import Frame, Signal, frames, fresh
from .theme import Theme

Color = str
Cap = Literal["butt", "round", "square"]
Join = Literal["miter", "round", "bevel"]
Align = Literal["left", "center", "right"]
Baseline = Literal["top", "middle", "alphabetic", "bottom"]
Points = Sequence[tuple[float, float]] | Any  # o un array de numpy de forma (n, 2)

# Color por defecto de las figuras y los trazos si no se indica `fill` ni `stroke`.
_DEFAULT_INK = "$primary"

# Verbos de `Path` (los mismos que `canvas.rs`).
_MOVE, _LINE, _QUAD, _CUBIC, _CLOSE, _ARC = range(6)


def _floats(values: Any) -> bytes:
    """`f32` nativos en bytes. Un array de numpy (o compatible) se convierte sin iterarlo."""
    astype = getattr(values, "astype", None)
    if astype is not None:
        return astype("=f4").tobytes()
    return array("f", values).tobytes()


def _points(points: Points) -> bytes:
    if hasattr(points, "astype"):
        return _floats(points)
    return array("f", chain.from_iterable(points)).tobytes()


class Path:
    """Trazado libre: líneas, curvas y arcos. Los métodos se encadenan:

    `Path().move_to(0, 0).line_to(40, 0).quad_to(60, 0, 60, 20).close()`
    """

    __slots__ = ("_data", "_verbs")

    def __init__(self) -> None:
        self._verbs = bytearray()
        self._data = array("f")

    def _add(self, verb: int, *values: float) -> Path:
        self._verbs.append(verb)
        self._data.extend(values)
        return self

    def move_to(self, x: float, y: float) -> Path:
        return self._add(_MOVE, x, y)

    def line_to(self, x: float, y: float) -> Path:
        return self._add(_LINE, x, y)

    def quad_to(self, cx: float, cy: float, x: float, y: float) -> Path:
        """Curva cuadrática hasta `(x, y)` con punto de control `(cx, cy)`."""
        return self._add(_QUAD, cx, cy, x, y)

    def cubic_to(self, c1x: float, c1y: float, c2x: float, c2y: float, x: float, y: float) -> Path:
        """Curva de Bézier cúbica hasta `(x, y)` con dos puntos de control."""
        return self._add(_CUBIC, c1x, c1y, c2x, c2y, x, y)

    def arc(self, cx: float, cy: float, r: float, start: float, sweep: float) -> Path:
        """Arco de circunferencia (ángulos en grados, 0 = derecha, sentido horario).
        Si el trazado ya tiene un punto, se une con una línea al inicio del arco."""
        return self._add(_ARC, cx, cy, r, start, sweep)

    def close(self) -> Path:
        return self._add(_CLOSE)


class Canvas:
    """Contexto de dibujo que recibe la función `draw` de un `canvas`.

    Coordenadas en píxeles lógicos, con el origen en la esquina superior
    izquierda de la caja de contenido (dentro del padding) y el eje y hacia
    abajo. Lo que se sale de la caja se recorta.

    Los colores aceptan tokens del tema (`"$primary"`) y hex con alfa
    (`"#7C5CFF80"`). Una figura se rellena con `fill`, se perfila con `stroke`
    (de grosor `stroke_width`) o ambas cosas; sin ninguno de los dos se rellena
    con `$primary`. `dash=(on, off, ...)` dibuja el trazo discontinuo.
    """

    __slots__ = ("_brushes", "_family", "_ops", "_theme", "height", "width")

    def __init__(self, width: float, height: float, theme: Theme) -> None:
        self.width = width
        self.height = height
        self._theme = theme
        self._family = theme.font_family
        self._ops: list[tuple[Any, ...]] = []
        self._brushes: dict[tuple[Any, ...], int] = {}

    # --- pinceles ----------------------------------------------------------

    def _color(self, color: Color) -> str:
        return self._theme.resolve(color) if color[:1] == "$" else color

    def _brush(
        self,
        fill: Color | None,
        stroke: Color | None,
        stroke_width: float,
        cap: Cap,
        join: Join,
        dash: Sequence[float] | None,
        default: Literal["fill", "stroke"],
    ) -> int:
        if fill is None and stroke is None:
            if default == "fill":
                fill = _DEFAULT_INK
            else:
                stroke = _DEFAULT_INK
        spec = (
            None if fill is None else self._color(fill),
            None if stroke is None else self._color(stroke),
            float(stroke_width),
            cap,
            join,
            None if dash is None else tuple(float(d) for d in dash),
        )
        # Los comandos referencian el pincel por índice: se envía una sola vez.
        index = self._brushes.get(spec)
        if index is None:
            index = self._brushes[spec] = len(self._brushes)
        return index

    def _batch(self) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
        return list(self._brushes), self._ops

    # --- figuras -----------------------------------------------------------

    def clear(self, color: Color = "$background") -> None:
        """Rellena todo el lienzo de un color."""
        self._ops.append(("clear", self._color(color)))

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        radius: float = 0,
        fill: Color | None = None,
        stroke: Color | None = None,
        stroke_width: float = 1,
        dash: Sequence[float] | None = None,
    ) -> None:
        brush = self._brush(fill, stroke, stroke_width, "butt", "miter", dash, "fill")
        self._ops.append(("rect", x, y, width, height, radius, brush))

    def oval(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        fill: Color | None = None,
        stroke: Color | None = None,
        stroke_width: float = 1,
        dash: Sequence[float] | None = None,
    ) -> None:
        """Elipse inscrita en el rectángulo `(x, y, width, height)`."""
        brush = self._brush(fill, stroke, stroke_width, "butt", "miter", dash, "fill")
        self._ops.append(("oval", x, y, width, height, brush))

    def circle(
        self,
        cx: float,
        cy: float,
        r: float,
        *,
        fill: Color | None = None,
        stroke: Color | None = None,
        stroke_width: float = 1,
        dash: Sequence[float] | None = None,
    ) -> None:
        brush = self._brush(fill, stroke, stroke_width, "butt", "miter", dash, "fill")
        self._ops.append(("circle", cx, cy, r, brush))

    def arc(
        self,
        cx: float,
        cy: float,
        r: float,
        start: float,
        sweep: float,
        *,
        pie: bool = False,
        fill: Color | None = None,
        stroke: Color | None = None,
        stroke_width: float = 1,
        cap: Cap = "butt",
        dash: Sequence[float] | None = None,
    ) -> None:
        """Arco de circunferencia (ángulos en grados, 0 = derecha, sentido horario).
        Sin `fill` se traza; `pie=True` lo cierra por el centro (sectores de un gráfico de tarta)."""
        brush = self._brush(fill, stroke, stroke_width, cap, "miter", dash, "fill" if pie else "stroke")
        self._ops.append(("arc", cx, cy, r, start, sweep, pie, brush))

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        stroke: Color = _DEFAULT_INK,
        stroke_width: float = 1,
        cap: Cap = "butt",
        dash: Sequence[float] | None = None,
    ) -> None:
        brush = self._brush(None, stroke, stroke_width, cap, "miter", dash, "stroke")
        self._ops.append(("line", x1, y1, x2, y2, brush))

    def polyline(
        self,
        points: Points,
        *,
        stroke: Color | None = None,
        fill: Color | None = None,
        stroke_width: float = 1,
        closed: bool = False,
        cap: Cap = "butt",
        join: Join = "round",
        dash: Sequence[float] | None = None,
    ) -> None:
        """Línea quebrada por `points` (pares `(x, y)` o un array de numpy de forma `(n, 2)`).
        Sin `stroke` ni `fill`, se traza con `$primary`."""
        brush = self._brush(fill, stroke, stroke_width, cap, join, dash, "stroke")
        self._ops.append(("poly", _points(points), closed, brush))

    def polygon(
        self,
        points: Points,
        *,
        fill: Color | None = None,
        stroke: Color | None = None,
        stroke_width: float = 1,
        join: Join = "miter",
        dash: Sequence[float] | None = None,
    ) -> None:
        """Polígono cerrado por `points`. Sin `fill` ni `stroke`, se rellena con `$primary`."""
        brush = self._brush(fill, stroke, stroke_width, "butt", join, dash, "fill")
        self._ops.append(("poly", _points(points), True, brush))

    def path(
        self,
        path: Path,
        *,
        fill: Color | None = None,
        stroke: Color | None = None,
        stroke_width: float = 1,
        cap: Cap = "butt",
        join: Join = "miter",
        dash: Sequence[float] | None = None,
    ) -> None:
        brush = self._brush(fill, stroke, stroke_width, cap, join, dash, "fill")
        self._ops.append(("path", bytes(path._verbs), path._data.tobytes(), brush))

    def text(
        self,
        x: float,
        y: float,
        content: object,
        *,
        color: Color = "$text",
        size: float = 14,
        weight: int = 400,
        family: str | None = None,
        align: Align = "left",
        baseline: Baseline = "top",
    ) -> None:
        """Texto en una línea. `align` lo coloca respecto a `x` y `baseline` respecto a `y`
        (`"top"`: `y` es su borde superior; `"middle"`, su centro; `"alphabetic"`, la línea base)."""
        self._ops.append(
            (
                "text",
                x,
                y,
                str(content),
                self._color(color),
                size,
                weight,
                family or self._family,
                align,
                baseline,
            )
        )

    # --- estado ------------------------------------------------------------

    def save(self) -> None:
        """Guarda la transformación y el recorte actuales (ver `restore` y `saved`)."""
        self._ops.append(("save",))

    def restore(self) -> None:
        self._ops.append(("restore",))

    @contextmanager
    def saved(self) -> Generator[Canvas]:
        """`save()` al entrar y `restore()` al salir: `with c.saved(): c.translate(...)`."""
        self.save()
        try:
            yield self
        finally:
            self.restore()

    def translate(self, dx: float, dy: float) -> None:
        self._ops.append(("translate", dx, dy))

    def scale(self, sx: float, sy: float | None = None) -> None:
        self._ops.append(("scale", sx, sx if sy is None else sy))

    def rotate(self, degrees: float) -> None:
        """Gira alrededor del origen actual (sentido horario)."""
        self._ops.append(("rotate", degrees))

    def clip_rect(self, x: float, y: float, width: float, height: float) -> None:
        """Recorta lo que se dibuje después a este rectángulo (hasta el próximo `restore`)."""
        self._ops.append(("clip", x, y, width, height))


class Drawing:
    """La función `draw` de un `canvas` ya ligada a un tema: lo que llama el núcleo.

    Recuerda los `Signal` que leyó la última vez: si el núcleo no fuerza el
    redibujado (mismo tamaño y misma función) y ninguno cambió, devuelve `None`
    y se conserva el dibujo anterior.
    """

    __slots__ = ("deps", "fn", "theme")

    def __init__(self, fn: Callable[[Canvas], Any], theme: Theme) -> None:
        self.fn = fn
        self.theme = theme
        self.deps: dict[Signal[Any], int] | None = None

    def __call__(self, width: float, height: float, force: bool) -> Any:
        if not force and self.deps is not None and fresh(self.deps):
            return None
        c = Canvas(width, height, self.theme)
        frame = Frame()
        stack = frames()
        stack.append(frame)
        try:
            self.fn(c)
        finally:
            stack.pop()
        self.deps = frame.deps
        return c._batch()


class CanvasElement(Element):
    __slots__ = ("draw",)

    def __init__(self, draw: Callable[[Canvas], Any], **props: Any) -> None:
        super().__init__("canvas", **props)
        self.draw = draw

    def _to_spec(self, theme: Theme) -> dict[str, Any]:
        spec = super()._to_spec(theme)
        spec["draw"] = Drawing(self.draw, theme)
        return spec


def canvas(draw: Callable[[Canvas], Any], **style: Any) -> Element:
    """Lienzo de dibujo inmediato: `draw(c)` recibe un `Canvas` del tamaño de la caja.

    Sin `height`, `grow` ni límites de alto mide 200 px de alto; a lo ancho se
    estira como cualquier caja. Admite el estilo de una caja (`bg`, `radius`,
    `padding`, `border_*`, `shadow`…) y manejadores como `on_click`.
    """
    if not callable(draw):
        raise TypeError("canvas: draw debe ser una función que reciba un Canvas")
    sized = {"height", "grow", "min_height", "max_height"}
    defaults = {} if sized & style.keys() else {"height": 200}
    return CanvasElement(draw, **{**defaults, **style})
