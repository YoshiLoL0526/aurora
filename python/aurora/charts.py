"""Gráficos nativos: línea, área, barras y dispersión.

`chart(y)` dibuja `y` como una línea; `kind="area"`, `"bar"` o `"scatter"`
cambian la forma. Los ejes se calculan solos (ticks redondos, rejilla y
etiquetas) y los datos cruzan al núcleo **sin copiarse**:

    chart(peticiones())                        # una línea
    chart(df, names=["p50", "p95"], kind="area")   # varias series
    chart(visitas, labels=MESES, kind="bar")       # barras por categoría
    chart(muestras, zoom=True)                 # millones de puntos, con rueda y arrastre

Un array de numpy o un `array.array` se leen de su propia memoria; una serie o
un DataFrame de polars se convierten con `to_numpy()`, que comparte memoria
cuando el tipo lo permite. Al dibujar, las series largas se reducen con LTTB
(~2 puntos por píxel): un gráfico de millones de puntos se sigue moviendo a
60 fps. Dentro de un `@component`, el gráfico solo se vuelve a dibujar cuando
cambian sus argumentos o algún `Signal` que lea el componente.
"""

from __future__ import annotations

from array import array
from collections.abc import Sequence
from typing import Any, Literal

from .elements import Element, _default_height
from .theme import Theme

Kind = Literal["line", "area", "bar", "scatter"]

_KINDS = ("line", "area", "bar", "scatter")

# Paleta de las series cuando no se indica `color` (tokens del tema).
_PALETTE = ("$primary", "$accent", "$success", "$danger", "$muted")


def _buffer(values: Any) -> memoryview:
    """Vista de `values` sin copiar sus datos.

    Un objeto que ya expone el protocolo de búfer (numpy, `array.array`,
    `memoryview`) se usa tal cual; uno con `to_numpy()` (polars, pandas) se
    convierte con él, y cualquier otra secuencia de números se empaqueta en un
    `array("d")` (la única copia, y solo para listas y tuplas).
    """
    if isinstance(values, memoryview):
        return values
    try:
        return memoryview(values)
    except TypeError:
        pass
    to_numpy = getattr(values, "to_numpy", None)
    if to_numpy is not None:
        return memoryview(to_numpy())
    return memoryview(array("d", values))


def _shape(mv: memoryview) -> tuple[int, ...]:
    """Forma del búfer (su `.shape` solo es `None` sin dimensiones, y aquí siempre hay)."""
    return mv.shape or (0,)


def _is_series(value: Any) -> bool:
    """`True` si `value` es una serie de datos y no un solo número."""
    if isinstance(value, (list, tuple, range)):
        return True
    try:
        view = memoryview(value)
    except TypeError:
        return hasattr(value, "to_numpy")
    # Un escalar de numpy (`np.float64(1.5)`) también expone un búfer, pero de
    # 0 dimensiones: es un número, no una serie (`list(array)` los da así).
    with view:
        return view.ndim > 0


def _columns(values: Any) -> list[tuple[memoryview, int]]:
    """Las series de `values`, como `(búfer, columna)`.

    `values` puede ser un búfer (una serie; si es 2-D `(n, m)`, una por columna:
    el núcleo lee cada columna con sus *strides*, sin trocear ni copiar nada) o
    una lista de series, cada una de ellas un búfer o una lista de números.
    """
    if isinstance(values, (list, tuple)) and values and _is_series(values[0]):
        series: list[tuple[memoryview, int]] = []
        for value in values:
            series.extend(_columns(value))
        return series
    mv = _buffer(values)
    if mv.ndim == 1:
        return [(mv, 0)]
    if mv.ndim == 2:
        columns = _shape(mv)[1]
        if columns == 0:
            raise ValueError("chart: los datos no tienen columnas")
        return [(mv, j) for j in range(columns)]
    raise ValueError(f"chart: los datos deben ser 1-D o 2-D (tienen {mv.ndim} dimensiones)")


def _colors(color: str | Sequence[str] | None, count: int) -> list[str]:
    """Un color por serie: el mismo, una lista que se repite, o la paleta del tema."""
    if color is None:
        return [_PALETTE[i % len(_PALETTE)] for i in range(count)]
    values = [color] if isinstance(color, str) else list(color)
    if not values:
        raise ValueError("chart: color no puede ser una lista vacía")
    for c in values:
        if not isinstance(c, str):
            raise TypeError(f"chart: color espera str o una lista de str, no {type(c).__name__}")
    return [values[i % len(values)] for i in range(count)]


class _Chart(Element):
    """Nodo `chart`. Los colores de las series y de los ejes se resuelven con el
    tema al serializar, como el resto del estilo."""

    __slots__ = ("options",)

    def __init__(self, options: dict[str, Any], **props: Any) -> None:
        super().__init__("chart", **props)
        self.options = options

    def _to_spec(self, theme: Theme) -> dict[str, Any]:
        spec = super()._to_spec(theme)
        options = dict(self.options)
        options["series"] = [(x, y, theme.resolve(c)) for x, y, c in options["series"]]
        options["label_color"] = theme.resolve(options["label_color"])
        options["grid_color"] = theme.resolve(options["grid_color"])
        options["family"] = theme.font_family
        spec["chart"] = options
        return spec


def chart(
    y: Any,
    *,
    x: Any = None,
    kind: Kind = "line",
    color: str | Sequence[str] | None = None,
    names: Sequence[Any] | None = None,
    labels: Sequence[Any] | None = None,
    y_min: float | None = None,
    y_max: float | None = None,
    grid: bool = True,
    zoom: bool = False,
    stroke_width: float = 2,
    point_size: float = 3.5,
    bar_width: float = 0.7,
    label_size: float = 11,
    label_color: str = "$muted",
    grid_color: str = "$border",
    **style: Any,
) -> Element:
    """Gráfico nativo alimentado por tus datos.

    `y` son los valores y puede ser:

    - un array de numpy, un `array.array`, un `memoryview` o una lista;
    - una lista de series (arrays o listas), una cada una;
    - una `Series` o un `DataFrame` de polars —o cualquier cosa con
      `to_numpy()`, como pandas—: un DataFrame aporta **una serie por columna**;
    - un array 2-D `(n, m)`: una serie por columna.

    Los datos **no se copian**: el núcleo los lee de la memoria del array (los
    de polars, mediante `to_numpy()`, que comparte memoria cuando el tipo lo
    permite). Los valores que falten (`NaN`) se saltan y, en una línea o un
    área, la cortan. Un gráfico de **millones de puntos** se reduce con LTTB al
    dibujarse (~2 puntos por píxel), sin perder los picos ni el perfil, y solo
    se leen los puntos visibles.

    Con varias series se dibuja una leyenda en la parte de arriba si hay
    `names`. El eje x son posiciones 0, 1, 2… salvo que des `x` (numérico) o
    `labels` (categorías: meses, días…), y el eje y se ajusta a los datos o a
    `y_min`/`y_max`. Las barras siempre nacen del cero.

    Con `zoom=True`, la rueda acerca y aleja sobre el puntero (que queda fijo
    en su dato), el arrastre desplaza la ventana y el doble clic vuelve a la
    vista completa; el eje y se ajusta a lo visible salvo que fijes
    `y_min`/`y_max`. Al llegar a un tope, la rueda sigue con el `scroll` de
    fuera.

    Admite el estilo de una caja (`bg`, `radius`, `padding`, `border_*`,
    `shadow`…), manejadores como `on_click` y una `height` (por defecto, 200 px
    de alto). En `kind="bar"`, los clics caen en el gráfico, no en cada barra.
    """
    if kind not in _KINDS:
        raise ValueError(f'chart: kind inválido: {kind!r} (usa "line", "area", "bar" o "scatter")')
    columns = _columns(y)
    if x is not None:
        if labels is not None:
            raise ValueError("chart: usa labels o x, pero no los dos")
        xs = (_buffer(x), 0)
        if xs[0].ndim != 1:
            raise ValueError("chart: x debe ser 1-D")
        length = _shape(xs[0])[0]
        for mv, _ in columns:
            if _shape(mv)[0] != length:
                raise ValueError(f"chart: x tiene {length} valores y hay series de {_shape(mv)[0]}")
    else:
        xs = None
    palette = _colors(color, len(columns))
    options: dict[str, Any] = {
        "kind": kind,
        "series": [(xs, (mv, col), tone) for (mv, col), tone in zip(columns, palette, strict=True)],
        "labels": None if labels is None else [str(v) for v in labels],
        "names": None if names is None else [str(v) for v in names],
        "y_min": y_min,
        "y_max": y_max,
        "grid": bool(grid),
        "zoom": bool(zoom),
        "stroke_width": stroke_width,
        "point_size": point_size,
        "bar_width": bar_width,
        "label_size": label_size,
        "label_color": label_color,
        "grid_color": grid_color,
    }
    return _Chart(options, **{**_default_height(style), **style})
