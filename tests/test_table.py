"""`table`: ordenación, columnas redimensionables y filas virtualizadas."""

from dataclasses import dataclass
from typing import Any

import pytest
from test_render import _png_pixel

from aurora import App, Column, Signal, column, table


@dataclass(frozen=True)
class Persona:
    nombre: str
    edad: int | None


PERSONAS = [Persona("carla", 31), Persona("Ana", 45), Persona("bruno", None), Persona("Diego", 31)]


def _names(pilot) -> list[str]:
    """Nombres en el orden en que se pintan las filas."""
    rows = []
    for i, p in enumerate(PERSONAS):
        rect = pilot.rect(f"t/row/{i}")
        if rect is not None:
            rows.append((rect[1], p.nombre))
    return [n for _, n in sorted(rows)]


def _pilot(rows: Any = PERSONAS, columns: Any = ("nombre", "edad"), size=(500, 300), **kw):
    view = lambda: column()[table(rows, list(columns), key="t", **kw)]
    pilot = App(view, size=size).pilot()
    pilot.settle()
    return pilot


def _center(rect):
    x, y, w, h = rect
    return x + w / 2, y + h / 2


def test_clicking_a_header_cycles_ascending_descending_original():
    pilot = _pilot()
    assert _names(pilot) == ["carla", "Ana", "bruno", "Diego"]
    pilot.click("t/h/nombre")
    assert _names(pilot) == ["Ana", "bruno", "carla", "Diego"]  # sin distinguir mayúsculas
    pilot.click("t/h/nombre")
    assert _names(pilot) == ["Diego", "carla", "bruno", "Ana"]
    pilot.click("t/h/nombre")
    assert _names(pilot) == ["carla", "Ana", "bruno", "Diego"]


def test_sort_is_stable_and_puts_missing_values_last():
    sort: Signal[Any] = Signal(("edad", False))
    pilot = _pilot(sort=sort)
    assert _names(pilot) == ["carla", "Diego", "Ana", "bruno"]
    sort.set(("edad", True))
    pilot.settle()
    # Los empates conservan su orden y los vacíos van al final también en descendente.
    assert _names(pilot) == ["Ana", "carla", "Diego", "bruno"]


def test_rows_can_be_dicts_tuples_or_objects():
    for rows in (
        [{"nombre": p.nombre, "edad": p.edad} for p in PERSONAS],
        [(p.nombre, p.edad) for p in PERSONAS],
        PERSONAS,
    ):
        pilot = _pilot(rows, sort=Signal(("nombre", False)))
        assert _names(pilot) == ["Ana", "bruno", "carla", "Diego"]


def test_value_format_and_unsortable_columns():
    sort: Signal[Any] = Signal(None)
    cols = [
        Column("nombre"),
        Column("largo", value=lambda p: len(p.nombre), format=lambda v: f"{v} letras"),
        Column("fijo", value=lambda p: 0, sortable=False),
    ]
    pilot = _pilot(columns=cols, sort=sort)
    pilot.click("t/h/largo")
    assert sort() == ("largo", False)
    assert _names(pilot) == ["Ana", "carla", "bruno", "Diego"]
    pilot.click("t/h/fijo")
    assert sort() == ("largo", False)


def test_dragging_the_header_edge_resizes_the_column():
    widths: Signal[dict[str, float]] = Signal({})
    cols = [Column("nombre", width=120, min_width=60), Column("edad", width=80)]
    pilot = _pilot(columns=cols, widths=widths)
    assert pilot.rect("t/h/nombre")[2] == 120
    pilot.move_to(*_center(pilot.rect("t/resize/nombre")))
    assert pilot.cursor == "col-resize"

    pilot.drag("t/resize/nombre", dx=50)
    assert widths() == {"nombre": 170}
    x, _, w, _ = pilot.rect("t/h/nombre")
    assert w == 170
    assert pilot.rect("t/h/edad")[0] == x + w  # la siguiente columna se desplaza

    pilot.drag("t/resize/nombre", dx=-500)
    assert widths()["nombre"] == 60  # no baja de min_width
    # Arrastrar el borde no ordena.
    assert _names(pilot) == ["carla", "Ana", "bruno", "Diego"]


@pytest.mark.parametrize("resizable", [True, False])
def test_resize_handle_only_when_resizable(resizable):
    pilot = _pilot(columns=[Column("nombre", resizable=resizable)])
    assert (pilot.rect("t/resize/nombre") is not None) == resizable


def test_only_visible_rows_are_built():
    rows = [{"n": i} for i in range(100_000)]
    pilot = _pilot(rows, columns=["n"], size=(400, 300))
    assert pilot.stats["nodes"] < 200
    assert pilot.rect("t/row/0") is not None
    assert pilot.rect("t/row/50") is None

    pilot.scroll("t/body", dy=36 * 50_000)
    pilot.settle()
    assert pilot.rect("t/row/0") is None
    assert pilot.rect("t/row/50000") is not None
    assert pilot.stats["nodes"] < 200


def test_sorting_is_memoized_while_scrolling():
    rows = [{"n": (i * 7919) % 100_000} for i in range(100_000)]
    calls = []

    def value(r):
        calls.append(1)
        return r["n"]

    pilot = _pilot(rows, columns=[Column("n", value=value)], sort=Signal(("n", True)))
    sorted_calls = len(calls)
    assert sorted_calls >= 100_000
    pilot.scroll("t/body", dy=36 * 1000)
    pilot.settle()
    # Al desplazarse solo se leen los valores de las celdas nuevas, sin volver a ordenar.
    assert len(calls) - sorted_calls < 200
    # 7919 es primo con 100 000: los valores son 0..99 999 y la fila 1000 del orden
    # descendente vale 98 999.
    shown = rows.index({"n": 98_999})
    assert pilot.rect(f"t/row/{shown}") is not None


def test_on_row_click_receives_the_row():
    chosen = []
    pilot = _pilot(on_row_click=chosen.append)
    pilot.click("t/row/1")
    assert chosen == [PERSONAS[1]]


def test_header_stays_fixed_while_the_body_scrolls():
    pilot = _pilot([{"n": i} for i in range(1000)], columns=["n"])
    header = pilot.rect("t/h/n")
    pilot.scroll("t/body", dy=2000)
    pilot.settle()
    assert pilot.scroll_offset("t/body") == (0, 2000)
    assert pilot.rect("t/h/n") == header


def test_wide_tables_scroll_horizontally():
    cols = [Column(f"c{i}", width=200) for i in range(5)]
    pilot = _pilot([{f"c{i}": i for i in range(5)}], columns=cols, size=(400, 200))
    pilot.scroll("t/h/c0", dx=300)
    pilot.settle()
    assert pilot.scroll_offset("t/x") == (300, 0)
    assert pilot.rect("t/h/c0")[0] < 0


def test_table_does_not_grow_with_its_rows():
    pilot = _pilot([{"n": i} for i in range(5000)], columns=["n"], size=(400, 300))
    assert pilot.rect("t")[3] == 300


def test_empty_table_shows_the_message():
    pilot = _pilot([], empty="Nada por aquí")
    assert pilot.rect("t/body") is None
    assert pilot.rect("t/h/nombre") is not None


def test_renders_header_rows_and_stripes(tmp_path):
    out = tmp_path / "table.png"
    rows = [{"a": "x" * (i + 1)} for i in range(6)]
    view = lambda: column()[table(rows, [Column("a", width=200)], key="t", row_height=30)]
    App(view, size=(300, 300)).render_png(str(out), scale=1.0)
    # Borde de 1 px, cabecera de 40 px y divisor de 1 px; luego filas de 30 px, la
    # segunda con franja.
    top = 1 + 40 + 1
    first = _png_pixel(out, 250, top + 15)
    second = _png_pixel(out, 250, top + 45)
    third = _png_pixel(out, 250, top + 75)
    assert first != second
    assert first == third
    # El texto de la primera celda se pinta.
    assert any(_png_pixel(out, x, top + 15) != first for x in range(13, 30))
