"""`chart`: gráficos nativos alimentados con numpy/polars sin copias."""

from array import array
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from test_render import _png_pixel, _png_rows

from aurora import MIDNIGHT, App, Signal, box, chart, column, component, scroll, text

# Márgenes del área de dibujo dentro de la caja del gráfico (los mismos que
# `chart/`): 8 px arriba y a la derecha, y la franja del eje x abajo.
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


@pytest.mark.parametrize("dtype", [">f8", ">f4", ">i4", ">u2"])
def test_big_endian_arrays_read_their_values(tmp_path, dtype):
    """Un array con el orden de bytes contrario al de la máquina no se lee como basura."""
    values = np.array([0, 3, 1], dtype=dtype)
    reference = _single(tmp_path, values.astype("=f8"), y_min=0, y_max=4)
    other = _single(tmp_path, values, y_min=0, y_max=4, name="be.png")
    assert reference.read_bytes() == other.read_bytes()


def test_a_list_of_numpy_scalars_is_one_series(tmp_path):
    """`list(array)` da escalares de numpy, que exponen un búfer 0-D: son números."""
    reference = _single(tmp_path, np.array([0.0, 1.0, 0.5]), y_min=0, y_max=1)
    for i, values in enumerate([list(np.array([0.0, 1.0, 0.5])), list(np.array([0, 1, 0.5], "f4"))]):
        other = _single(tmp_path, values, y_min=0, y_max=1, name=f"s{i}.png")
        assert reference.read_bytes() == other.read_bytes()


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
    # La rejilla va discontinua (trazo a rayas), así que se cuenta el total y no
    # un tramo: con rejilla hay ~80 píxeles, y sin ella solo motas sueltas del
    # anti-aliasing del trazo o de la fuente (menos de 30 en cualquier plataforma).
    border = (0x25, 0x2B, 0x3B)  # "$border" del tema MIDNIGHT
    with_grid = _pixels(_single(tmp_path, np.array([0.0, 1.0]), y_min=0, y_max=1), border, tol=6)
    assert len(with_grid) >= 30
    out = _single(tmp_path, np.array([0.0, 1.0]), y_min=0, y_max=1, grid=False, name="no.png")
    assert len(_pixels(out, border, tol=3)) < 30


# --- millones de puntos (reducción con LTTB) ----------------------------------


def test_a_million_points_keep_the_spike(tmp_path):
    """Un pico único en un millón de puntos sobrevive a la reducción."""
    n = 1_000_000
    y = np.zeros(n)
    y[500_000] = 1.0
    pilot = App(
        lambda: box(bg="#000000")[chart(y, color="#FF0000", key="c", grow=1)],
        size=(SIZE, SIZE),
    ).pilot()
    out = tmp_path / "million.png"
    pilot.png(str(out))
    pixels = _pixels(out, RED)
    top = [p for p in pixels if p[1] <= TOP + 4]
    assert top, "el pico no sobrevivió a la reducción"
    # En el centro del área de dibujo (500 000 de 999 999) y sin engordar la línea.
    xs = [p[0] for p in pixels]
    mid = (min(xs) + max(xs)) / 2
    assert all(abs(p[0] - mid) <= 4 for p in top)
    # Reducir un millón de puntos cuesta milisegundos, no segundos.
    assert pilot.stats["draw"] < 2000


def test_downsampling_keeps_the_shape(tmp_path):
    """La misma señal a 1 000 000 y a 10 000 puntos se ve igual."""
    big = np.sin(np.linspace(0.0, 40 * np.pi, 1_000_000))
    small = np.sin(np.linspace(0.0, 40 * np.pi, 10_000))
    a = _bounds(_pixels(_single(tmp_path, big, name="big.png"), RED))
    b = _bounds(_pixels(_single(tmp_path, small, name="small.png"), RED))
    assert abs(a[0] - b[0]) <= 3  # izquierda
    assert abs(a[1] - b[1]) <= 5  # arriba (los picos)
    assert abs(a[2] - b[2]) <= 3  # derecha
    assert abs(a[3] - b[3]) <= 5  # abajo (los valles)


def test_downsampling_keeps_the_gaps(tmp_path):
    """Un hueco de `NaN` en el centro de 100 000 puntos sigue cortando la línea."""
    n = 100_000
    y = np.full(n, 0.5)
    y[40_000:60_000] = np.nan
    pixels = _pixels(_single(tmp_path, y), RED)
    assert [p for p in pixels if p[0] < 60]
    assert [p for p in pixels if p[0] > 140]
    # El hueco ocupa del 40 % al 60 % del ancho del área de dibujo (~30..192).
    assert not [x for x, _ in pixels if 100 < x < 122]


def test_a_closed_curve_is_not_reduced_to_a_line(tmp_path):
    """Con x desordenada (aquí un círculo, que empieza y acaba en la misma x), el
    presupuesto de la reducción no sale del ancho entre el primer y el último punto."""
    t = np.linspace(0.0, 2 * np.pi, 200)
    x0, y0, x1, y1 = _bounds(_pixels(_single(tmp_path, np.sin(t), x=np.cos(t)), RED))
    assert x1 - x0 > 120 and y1 - y0 > 120  # sigue siendo un círculo


# --- zoom y pan ---------------------------------------------------------------


def _zoomable(data=None, **chart_kwargs):
    """Un gráfico rojo con zoom que ocupa 200×200, y su piloto."""
    values = np.linspace(0.0, 1.0, 501) if data is None else data
    chart_kwargs.setdefault("zoom", True)
    chart_kwargs.setdefault("color", "#FF0000")
    return (
        App(
            lambda: box(bg="#000000")[chart(values, key="c", grow=1, **chart_kwargs)],
            size=(SIZE, SIZE),
        ).pilot(),
        values,
    )


def _center(pilot, key="c"):
    """Centro del nodo `key` en el último frame."""
    x, y, w, h = pilot.rect(key)
    return x + w / 2, y + h / 2


def test_zoom_uses_the_pointer_as_the_anchor():
    pilot, _ = _zoomable()
    assert pilot.chart_view("c") == (0.0, 500.0)  # sin zoom, el dominio completo
    x, y, w, h = pilot.rect("c")
    pilot.move_to(x + w * 0.25, y + h / 2)
    pilot.wheel(-1, lines=True)  # rueda arriba: acerca
    left = pilot.chart_view("c")
    assert left is not None
    assert left[1] - left[0] == pytest.approx(400.0, rel=1e-6)  # un paso de 1,25×
    # Anclado a la izquierda: el borde izquierdo apenas se mueve y el derecho se acerca.
    assert left[0] < 500.0 - left[1]

    other, _ = _zoomable()
    x, y, w, h = other.rect("c")
    other.move_to(x + w * 0.75, y + h / 2)
    other.wheel(-1, lines=True)
    right = other.chart_view("c")
    assert right is not None
    assert right[1] - right[0] == pytest.approx(400.0, rel=1e-6)
    # Anclado a la derecha: es el borde derecho el que apenas se mueve.
    assert 500.0 - right[1] < right[0]

    # Y la rueda hacia el otro lado vuelve al dominio completo.
    other.wheel(1, lines=True)
    assert other.chart_view("c") == (0.0, 500.0)


def test_zoom_uses_the_x_values_when_the_series_has_them():
    n = 100_000
    x = np.linspace(1000.0, 2000.0, n)
    pilot, _ = _zoomable(np.sin(x), x=x)
    assert pilot.chart_view("c") == (1000.0, 2000.0)
    pilot.move_to(*_center(pilot))
    pilot.wheel(-1, lines=True)
    view = pilot.chart_view("c")
    assert view is not None
    span = view[1] - view[0]
    assert span == pytest.approx(800.0, abs=1.0)
    assert 1000.0 < view[0] < 1200.0  # el ancla está en el centro, no en un borde
    assert 1800.0 < view[1] < 2000.0


def test_zoom_and_pan_stay_inside_the_data():
    pilot, _ = _zoomable()
    x, y, w, h = pilot.rect("c")
    # Encadenar 200 pasos no puede salirse del dominio ni degenerar la ventana.
    pilot.move_to(x + w / 2, y + h / 2)
    for _ in range(200):
        pilot.wheel(-1, lines=True)
    view = pilot.chart_view("c")
    assert view is not None
    assert 0.0 <= view[0] < view[1] <= 500.0
    assert view[1] - view[0] > 0.0


def test_drag_pans_the_window():
    pilot, _ = _zoomable()
    cx, cy = _center(pilot)
    pilot.move_to(cx, cy)
    pilot.wheel(-1, lines=True)
    before = pilot.chart_view("c")
    assert before is not None
    pilot.mouse_down()
    pilot.move_to(cx + 40, cy)
    after = pilot.chart_view("c")
    pilot.mouse_up()
    assert after is not None
    assert after[1] < before[1]  # el contenido sigue al puntero: la ventana se va
    assert after[0] < before[0]
    assert after[1] - after[0] == pytest.approx(before[1] - before[0])  # mismo ancho
    assert pilot.chart_view("c") == after  # soltar no mueve nada más


def test_a_drag_does_not_complete_the_click():
    clicks: list[int] = []
    pilot, _ = _zoomable(on_click=lambda: clicks.append(1))
    cx, cy = _center(pilot)
    pilot.move_to(cx, cy)
    pilot.mouse_down()
    pilot.move_to(cx + 30, cy)
    pilot.mouse_up()
    assert clicks == []
    pilot.click("c")  # un clic sin arrastre sí llega
    assert clicks == [1]


def test_double_click_returns_to_the_full_view():
    pilot, _ = _zoomable()
    cx, cy = _center(pilot)
    pilot.move_to(cx, cy)
    pilot.wheel(-1, lines=True)
    assert pilot.chart_view("c") != (0.0, 500.0)
    pilot.click_at(cx, cy)
    pilot.click_at(cx, cy)  # dos clics seguidos: doble clic
    assert pilot.chart_view("c") == (0.0, 500.0)


def test_zoom_adjusts_the_y_axis_to_what_is_visible(tmp_path):
    """Sin `y_min`/`y_max`, el eje y se ajusta a la ventana visible."""
    y = np.zeros(1000)
    y[800:] = 1.0
    pilot, _ = _zoomable(y)
    before = tmp_path / "before.png"
    pilot.png(str(before))
    # Con el dominio completo (0..1), el cero está abajo del todo.
    assert max(p[1] for p in _pixels(before, RED)) > 160

    # Acercar sobre la zona plana (la izquierda): solo se ve el cero.
    x, top, w, h = pilot.rect("c")
    pilot.move_to(x + w * 0.2, top + h / 2)
    for _ in range(3):
        pilot.wheel(-1, lines=True)
    after = tmp_path / "after.png"
    pilot.png(str(after))
    rows = [p[1] for p in _pixels(after, RED)]
    assert min(rows) > 60 and max(rows) < 130  # la línea queda a media altura


def test_without_zoom_the_chart_does_not_capture_the_wheel():
    pilot, _ = _zoomable(zoom=False)
    cx, cy = _center(pilot)
    pilot.move_to(cx, cy)
    pilot.wheel(-1, lines=True)
    pilot.mouse_down()
    pilot.move_to(cx + 40, cy)
    pilot.mouse_up()
    assert pilot.chart_view("c") == (0.0, 500.0)  # ni rueda ni arrastre lo mueven


def test_zoom_works_on_every_kind(tmp_path):
    """Línea, área, barras y dispersión comparten la ventana del zoom."""
    for kind in ("line", "area", "bar", "scatter"):
        pilot, _ = _zoomable(kind=kind)
        pilot.move_to(*_center(pilot))
        pilot.wheel(-1, lines=True)
        view = pilot.chart_view("c")
        assert view is not None and view[1] - view[0] < 500.0, kind
        out = tmp_path / f"{kind}.png"
        pilot.png(str(out))
        assert _pixels(out, RED), f"nada dibujado en {kind}"


def test_zoom_with_several_series(tmp_path):
    a = np.linspace(0.0, 1.0, 1000)
    pilot, _ = _zoomable(np.column_stack([a, 1.0 - a]), color=["#FF0000", "#00FF00"])
    pilot.move_to(*_center(pilot))
    pilot.wheel(-1, lines=True)
    out = tmp_path / "series.png"
    pilot.png(str(out))
    assert _pixels(out, RED)
    assert _pixels(out, (0, 255, 0))


def test_zoom_with_a_descending_x(tmp_path):
    """x en orden descendente: la ventana se acota igual (búsqueda al revés)."""
    n = 10_000
    x = np.linspace(1000.0, 0.0, n)
    pilot, _ = _zoomable(np.sin(x / 100), x=x)
    assert pilot.chart_view("c") == (0.0, 1000.0)
    pilot.move_to(*_center(pilot))
    pilot.wheel(-1, lines=True)
    view = pilot.chart_view("c")
    assert view is not None
    assert 400.0 < view[1] - view[0] < 900.0  # se acercó…
    assert 0.0 <= view[0] < view[1] <= 1000.0
    out = tmp_path / "descendente.png"
    pilot.png(str(out))
    assert _pixels(out, RED)  # y la línea se sigue dibujando


def test_zoom_with_an_unsorted_x(tmp_path):
    """Con x desordenada no hay búsqueda binaria: se filtra punto a punto."""
    rng = np.random.default_rng(3)
    n = 5_000
    x = rng.uniform(0.0, 100.0, n)
    pilot, _ = _zoomable(np.sin(x), x=x)
    pilot.move_to(*_center(pilot))
    pilot.wheel(-1, lines=True)
    view = pilot.chart_view("c")
    assert view is not None and view[1] - view[0] < 100.0
    out = tmp_path / "desordenada.png"
    pilot.png(str(out))
    assert _pixels(out, RED)


def test_the_zoom_window_survives_a_rebuild():
    """La ventana es estado por key: unos datos nuevos no la resetean."""
    version = Signal(0)
    data = np.linspace(0.0, 1.0, 1001)
    pilot = App(
        lambda: box(bg="#000000")[chart(data * (version() + 1), color="#FF0000", key="c", grow=1, zoom=True)],
        size=(SIZE, SIZE),
    ).pilot()
    pilot.move_to(*_center(pilot))
    pilot.wheel(-1, lines=True)
    before = pilot.chart_view("c")
    assert before is not None
    version.set(1)  # datos nuevos, misma x: la ventana se conserva
    pilot.frame()
    assert pilot.chart_view("c") == before


def test_chart_view_is_none_for_other_nodes():
    pilot, _ = _zoomable()
    assert pilot.chart_view("no-existe") is None


def test_the_wheel_falls_through_to_the_scroll_at_the_limit():
    """Al llegar al tope, la rueda sigue con el `scroll` de fuera."""
    pilot = App(
        lambda: scroll(key="s", height=100)[
            chart(np.linspace(0.0, 1.0, 50), key="c", height=400, zoom=True, color="#FF0000")
        ],
        size=(200, 200),
    ).pilot()
    cx, cy = _center(pilot)
    pilot.move_to(cx, min(cy, 90))
    pilot.wheel(1)  # hacia fuera sin zoom: no hay tope que pasar…
    assert pilot.chart_view("c") == (0.0, 49.0)  # …y el scroll se mueve
    assert pilot.scroll_offset("s") == (0.0, 1.0)
    pilot.wheel(-1)  # hacia dentro: se acerca y el scroll no se toca
    assert pilot.chart_view("c") != (0.0, 49.0)
    assert pilot.scroll_offset("s") == (0.0, 1.0)


def test_segments_crossing_the_edge_keep_their_slope(tmp_path):
    """Con zoom, el segmento que cruza el borde se corta en él (interpolado) en vez
    de pegar el punto de fuera al borde, que cambiaría su pendiente."""
    pilot, _ = _zoomable(np.array([0.0, 10.0, 0.0, 10.0]), y_min=0, y_max=10)
    pilot.move_to(*_center(pilot))
    for _ in range(8):
        pilot.wheel(-1, lines=True)
    view = pilot.chart_view("c")
    assert view is not None and view[0] > 1.0 and view[1] < 2.0  # dentro del tramo 10 → 0
    out = tmp_path / "edge.png"
    pilot.png(str(out))
    pixels = _pixels(out, RED)
    x0, y0, _, y1 = _bounds(pixels)
    # La línea baja de 10 - 10·(x0 - 1) a 10 - 10·(x1 - 1): ni toca el tope ni el suelo…
    plot_h = SIZE - BOTTOM - TOP
    assert y0 > TOP + plot_h * (view[0] - 1.0) - 6
    assert y1 < TOP + plot_h * (view[1] - 1.0) + 6
    # …y no hay una línea vertical falsa pegada al borde izquierdo.
    edge = [y for x, y in pixels if x == x0]
    assert max(edge) - min(edge) < 12


def test_zoom_with_gaps_in_x_keeps_the_points_after_the_gap(tmp_path):
    """Un `NaN` en x no debe confundir la búsqueda de la ventana visible."""
    x = np.arange(1000, dtype=float)
    x[750] = np.nan
    pilot, _ = _zoomable(np.ones(1000), x=x, y_min=0, y_max=2)
    px, py, w, h = pilot.rect("c")
    pilot.move_to(px + w * 0.75, py + h / 2)
    for _ in range(6):
        pilot.wheel(-1, lines=True)
    view = pilot.chart_view("c")
    assert view is not None and view[0] < 740 and view[1] > 760  # el hueco queda dentro
    out = tmp_path / "gap.png"
    pilot.png(str(out))
    pixels = _pixels(out, RED)
    assert _bounds(pixels)[2] >= SIZE - RIGHT - 3  # la línea llega al borde derecho


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
