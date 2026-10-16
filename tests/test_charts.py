"""`chart`: gráficos nativos alimentados con numpy/polars sin copias."""

from array import array
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from test_render import _png_pixel, _png_rows

from aurora import MIDNIGHT, App, Signal, box, chart, column, component, text

# Márgenes del área de dibujo dentro de la caja del gráfico (los mismos que
# `chart.rs`): 8 px arriba y a la derecha, y la franja del eje x abajo.
TOP, RIGHT = 8, 8
BOTTOM = 11 * 1.5 + 6
SIZE = 200

RED = (255, 0, 0)


def _render(tmp_path, view, size=(SIZE, SIZE), name="out.png"):
    out = tmp_path / name
    App(view, size=size).render_png(str(out), scale=1.0)
    return out


def _pixels(path: Path, color: tuple[int, int, int], tol: int = 40) -> list[tuple[int, int]]:
    """Píxeles del PNG cuyo color se parece a `color` (para encontrar figuras)."""
    channels, rows = _png_rows(path)
    return [
        (x, y)
        for y, row in enumerate(rows)
        for x in range(len(row) // channels)
        if max(abs(row[x * channels + i] - color[i]) for i in range(3)) <= tol
    ]


def _bounds(pixels: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    xs = [p[0] for p in pixels]
    ys = [p[1] for p in pixels]
    return min(xs), min(ys), max(xs), max(ys)


def _rgb(color: str) -> tuple[int, int, int]:
    """Un color `"#rrggbb"` del tema como tupla de canales."""
    return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))


def _single(tmp_path, y, *, name="out.png", **style):
    """Renderiza un gráfico (rojo salvo que `style` diga otra cosa) que ocupa 200×200."""
    style.setdefault("color", "#FF0000")
    return _render(
        tmp_path,
        lambda: box(bg="#000000")[chart(y, key="c", **style)],
        name=name,
    )


# --- figuras ----------------------------------------------------------------


def test_line_spans_the_plot_with_a_fixed_range(tmp_path):
    out = _single(tmp_path, np.array([0.0, 1.0]), x=np.array([0.0, 10.0]), y_min=0, y_max=1)
    x0, y0, x1, y1 = _bounds(_pixels(out, RED))
    assert x0 <= 30 and x1 >= SIZE - RIGHT - 30  # de borde a borde del área
    assert TOP - 3 <= y0 <= TOP + 3  # el máximo toca el tick de arriba
    assert SIZE - BOTTOM - 3 <= y1 <= SIZE - BOTTOM + 3  # el mínimo, el de abajo


def test_the_value_maps_upwards(tmp_path):
    low = _pixels(_single(tmp_path, np.full(3, 0.2), y_min=0, y_max=1), RED)
    high = _pixels(_single(tmp_path, np.full(3, 0.8), y_min=0, y_max=1, name="high.png"), RED)
    assert _bounds(high)[1] < _bounds(low)[1] - 30


def test_a_single_point_is_a_dot(tmp_path):
    x0, y0, x1, y1 = _bounds(_pixels(_single(tmp_path, np.array([1.0]), y_min=0, y_max=1), RED))
    assert x1 - x0 <= 6 and y1 - y0 <= 6


def test_area_fills_down_to_zero(tmp_path):
    out = _single(tmp_path, np.full(2, 0.8), kind="area", y_min=0, y_max=1)
    for x in (90, 110):
        assert _png_pixel(out, x, 100) != (0, 0, 0)  # relleno bajo la curva
        assert _png_pixel(out, x, 20) == (0, 0, 0)  # y nada por encima


def test_bars_grow_from_zero_and_negative_values_hang_below(tmp_path):
    out = _single(tmp_path, np.array([-1.0, 1.0]), kind="bar", y_min=-1, y_max=1, bar_width=0.9)
    # Dos barras, en el centro de cada mitad; el cero queda a media altura.
    assert _png_pixel(out, 60, 150) != (0, 0, 0)  # la primera, negativa: bajo el cero
    assert _png_pixel(out, 60, 60) == (0, 0, 0)
    assert _png_pixel(out, 140, 60) != (0, 0, 0)  # la segunda, positiva: encima
    assert _png_pixel(out, 140, 150) == (0, 0, 0)


def test_bars_of_several_series_are_grouped(tmp_path):
    y = np.array([[1.0, 1.0]])  # un punto, dos series
    out = _single(tmp_path, y, kind="bar", color=["#FF0000", "#00FF00"], y_min=0, y_max=1)
    red = [x for x, _ in _pixels(out, RED)]
    green = [x for x, _ in _pixels(out, (0, 255, 0))]
    assert red and green
    assert max(red) < min(green)  # una al lado de la otra, no superpuestas


def test_scatter_draws_points_where_the_values_are(tmp_path):
    out = _single(tmp_path, np.array([0.05, 0.95]), x=np.array([1.0, 1.0]), kind="scatter", y_min=0, y_max=1)
    x0, y0, x1, y1 = _bounds(_pixels(out, RED))
    assert x1 - x0 <= 6  # los dos puntos, en la misma x
    assert y1 - y0 > 100  # y separados en vertical
    assert _png_pixel(out, (x0 + x1) // 2, (y0 + y1) // 2) == (0, 0, 0)  # sin línea entre ellos


def test_missing_values_break_the_line(tmp_path):
    y = np.array([1.0, 1.0, np.nan, 1.0, 1.0])
    red = _pixels(_single(tmp_path, y, y_min=0, y_max=1), RED)
    xs = sorted({x for x, _ in red})
    assert xs[0] < 60 and xs[-1] > 140  # los dos tramos se pintan
    assert not [x for x in xs if 80 < x < 140]  # el hueco queda vacío


def test_reversed_data_flips_the_line(tmp_path):
    y = np.linspace(0.0, 1.0, 20)

    def ends(pixels):
        left = max(y for x, y in pixels if x < 40)
        right = max(y for x, y in pixels if x > SIZE - RIGHT - 30)
        return left, right

    normal = ends(_pixels(_single(tmp_path, y, y_min=0, y_max=1), RED))
    flipped = ends(_pixels(_single(tmp_path, y[::-1], y_min=0, y_max=1, name="f.png"), RED))
    assert normal[0] > normal[1]  # empieza abajo a la izquierda
    assert flipped[0] < flipped[1]  # la vista invertida, arriba


# --- datos ------------------------------------------------------------------


@pytest.mark.parametrize(
    "values",
    [
        pl.Series([0.0, 1.0, 0.5]),
        array("d", [0.0, 1.0, 0.5]),
        [0.0, 1.0, 0.5],
        memoryview(np.array([0.0, 1.0, 0.5])),
        [pl.Series([0.0, 1.0, 0.5])],
    ],
    ids=["polars", "array", "lista", "memoryview", "lista-de-series"],
)
def test_the_same_data_renders_the_same(tmp_path, values):
    reference = _single(tmp_path, np.array([0.0, 1.0, 0.5]), y_min=0, y_max=1)
    other = _single(tmp_path, values, y_min=0, y_max=1, name="other.png")
    assert reference.read_bytes() == other.read_bytes()


def test_polars_dataframe_is_one_series_per_column(tmp_path):
    df = pl.DataFrame({"a": [0.0, 1.0, 0.0], "b": [0.0, 0.0, 1.0]})
    out = _single(tmp_path, df, color=None, y_min=0, y_max=1, names=["a", "b"])
    primary = _rgb(MIDNIGHT.colors["primary"])
    accent = _rgb(MIDNIGHT.colors["accent"])
    # Las dos series, con la paleta del tema (en el dibujo, no solo en la leyenda).
    assert [p for p in _pixels(out, primary, tol=20) if p[1] > 30]
    assert [p for p in _pixels(out, accent, tol=20) if p[1] > 30]


def test_numpy_columns_of_a_matrix(tmp_path):
    m = np.array([[0.0, 1.0], [1.0, 1.0], [0.5, 0.0]])
    out = _single(tmp_path, m, color=["#FF0000", "#00FF00"], y_min=0, y_max=1)
    assert _pixels(out, RED)
    assert _pixels(out, (0, 255, 0))


def test_fortran_and_integer_arrays(tmp_path):
    m = np.asfortranarray(np.array([[1.0, 3.0], [2.0, 4.0]]))
    assert _pixels(_single(tmp_path, m, kind="bar", y_min=0, y_max=5), RED)
    series = pl.Series([3, 1, 2])  # enteros de polars
    assert _pixels(_single(tmp_path, series, kind="bar", y_min=0, y_max=4, name="i.png"), RED)


# --- sin copias --------------------------------------------------------------


def test_renders_the_live_memory_of_the_array(tmp_path):
    """Releer el gráfico relee el array: mutarlo en sitio se ve sin volver a pasarlo."""
    values = np.zeros(50)
    version = Signal(0)
    pilot = App(
        lambda: box(bg="#000000")[chart(values, color=("#00FF00" if version() == 0 else "#FF0000"), grow=1)],
        size=(SIZE, SIZE),
    ).pilot()
    out = tmp_path / "live.png"
    pilot.png(str(out))
    assert not _pixels(out, RED)  # verde (valores a cero)
    values[:] = 1.0  # en sitio: el mismo búfer
    version.set(1)
    pilot.frame()
    pilot.png(str(out))
    assert _pixels(out, RED)  # la memoria es la del array, no una foto del parseo


def test_the_view_keeps_the_buffer_alive(tmp_path):
    """Aunque Python suelte el array, el núcleo conserva su memoria."""
    holder = [np.linspace(0.0, 1.0, 30)]
    pilot = App(
        lambda: box(bg="#000000")[chart(holder[0], color="#FF0000", y_min=0, y_max=1, grow=1)],
        size=(SIZE, SIZE),
    ).pilot()
    out = tmp_path / "alive.png"
    pilot.png(str(out))
    before = _bounds(_pixels(out, RED))
    holder.clear()  # el gráfico se queda como el único dueño del búfer
    pilot.resize(300, SIZE)  # vuelve a grabar el mismo dato con otra caja
    pilot.png(str(out))
    after = _bounds(_pixels(out, RED))
    assert after[2] - after[0] > before[2] - before[0]  # se re-grabó, más ancho


def test_resize_regenerates_the_picture(tmp_path):
    values = np.linspace(0.0, 1.0, 20)
    pilot = App(
        lambda: box(bg="#000000")[chart(values, color="#FF0000", y_min=0, y_max=1, grow=1)],
        size=(SIZE, 100),
    ).pilot()
    small, big = tmp_path / "small.png", tmp_path / "big.png"
    pilot.png(str(small))
    pilot.resize(400, 100)
    pilot.png(str(big))
    xs_small = {x for x, _ in _pixels(small, RED)}
    xs_big = {x for x, _ in _pixels(big, RED)}
    assert max(xs_big) - min(xs_big) > max(xs_small) - min(xs_small) + 150


# --- cuándo se vuelve a grabar ------------------------------------------------


def test_memoized_chart_redraws_only_when_its_data_changes():
    data = np.zeros(10)
    other = Signal(0)
    version = Signal(0)
    calls: list[int] = []

    @component
    def grafico(_version: int):
        calls.append(_version)
        return chart(data, color="#FF0000", y_min=0, y_max=1, key="c", height=60)

    def view():
        other()
        return column()[grafico(version()), text("hola", key="t")]

    pilot = App(view, size=(SIZE, 120)).pilot()
    assert calls == [0]
    other.set(1)  # reconstruye la vista, pero no el componente del gráfico
    pilot.frame()
    assert pilot.stats["rebuilt"] and calls == [0]
    assert pilot.stats["damage"] is None  # no se repintó nada (tampoco el gráfico)
    data[:] = 1.0  # el dato mutado no basta: el componente sigue memorizado
    version.set(1)  # y al cambiar su argumento se reconstruye y se vuelve a grabar
    pilot.frame()
    assert calls == [0, 1]
    assert pilot.stats["damage"] == (0, 0, SIZE, 61)  # solo la caja del gráfico


# --- ejes y etiquetas ---------------------------------------------------------


def test_labels_are_painted_under_the_axis(tmp_path):
    out = _single(
        tmp_path,
        np.array([1.0, 2.0, 3.0]),
        kind="bar",
        labels=["lunes", "martes", "miércoles"],
        label_color="#00FF00",
    )
    strip = [p for p in _pixels(out, (0, 255, 0)) if p[1] > SIZE - BOTTOM - 4]
    xs = sorted({x for x, _ in strip})
    assert xs[0] < 70 and xs[-1] > 130  # los textos se reparten por el ancho


def test_ticks_respect_the_fixed_range(tmp_path):
    out = _single(
        tmp_path,
        np.array([0.0]),
        y_min=0,
        y_max=1000,
        grid_color="#0000FF",
        label_color="#000000",
    )
    # Tolerancia alta: un trazo de 1 px se mezcla con el fondo en los bordes.
    rows = sorted({y for _, y in _pixels(out, (0, 0, 255), tol=150)})
    assert TOP - 3 <= rows[0] <= TOP + 3  # el tick de 1000, arriba del todo
    assert SIZE - BOTTOM - 3 <= rows[-1] <= SIZE - BOTTOM + 3  # el de cero, abajo


def test_grid_can_be_turned_off(tmp_path):
    border = (0x25, 0x2B, 0x3B)  # "$border" del tema MIDNIGHT
    assert _pixels(_single(tmp_path, np.array([0.0, 1.0]), y_min=0, y_max=1), border, tol=6)
    out = _single(tmp_path, np.array([0.0, 1.0]), y_min=0, y_max=1, grid=False, name="no.png")
    assert not _pixels(out, border, tol=6)


# --- interacción y errores ----------------------------------------------------


def test_the_example_updates_on_a_click(tmp_path):
    """`examples/charts.py` de punta a punta: el botón reescribe los datos y el gráfico."""
    import runpy

    module = runpy.run_path(str(Path(__file__).parent.parent / "examples" / "charts.py"), run_name="charts")
    pilot = module["app"].pilot(size=(980, 620))
    before, after = tmp_path / "before.png", tmp_path / "after.png"
    pilot.png(str(before))
    pilot.click("nuevo-dato")
    assert module["version"]() == 1
    pilot.png(str(after))
    assert before.read_bytes() != after.read_bytes()


def test_chart_receives_clicks():
    clicks: list[int] = []
    view = lambda: column()[chart(np.zeros(3), key="c", height=50, on_click=lambda: clicks.append(1))]
    pilot = App(view, size=(100, 100)).pilot()
    pilot.click("c")
    assert clicks == [1]


def test_invalid_kind():
    with pytest.raises(ValueError, match="kind"):
        chart(np.zeros(3), kind="tarta")  # ty: ignore[invalid-argument-type]


def test_names_must_match_the_series():
    with pytest.raises(ValueError, match="nombres"):
        App(lambda: chart([np.zeros(3), np.zeros(3)], names=["solo una"]), size=(100, 100)).pilot()


def test_labels_must_match_the_points():
    with pytest.raises(ValueError, match="etiquetas"):
        App(lambda: chart(np.zeros(3), labels=["a"], kind="bar"), size=(100, 100)).pilot()


def test_x_and_labels_are_exclusive():
    with pytest.raises(ValueError, match="no los dos"):
        chart(np.zeros(3), x=np.zeros(3), labels=["a", "b", "c"])


def test_x_must_match_the_series():
    with pytest.raises(ValueError, match="x tiene"):
        chart(np.zeros(4), x=np.zeros(3))


def test_y_range_must_be_consistent():
    with pytest.raises(ValueError, match="y_max"):
        App(lambda: chart(np.zeros(3), y_min=2, y_max=1), size=(100, 100)).pilot()


def test_color_must_be_a_string():
    with pytest.raises(TypeError, match="color"):
        chart(np.zeros(3), color=[1, 2])  # ty: ignore[invalid-argument-type]


def test_non_numeric_data_raises():
    with pytest.raises(ValueError, match="tipo de dato"):
        App(lambda: chart(np.array([1 + 2j, 3 + 0j])), size=(100, 100)).pilot()
    with pytest.raises(TypeError):
        chart("no son números")
