"""`virtual_list` y `on_scroll`: solo se construye lo visible y se sigue al desplazamiento."""

import pytest

from aurora import App, Signal, column, component, row, scroll, text, virtual_list


def _list(count=10_000, *, size=(300, 200), key="lista", **kw):
    built = []

    def item(i: int):
        built.append(i)
        return row(grow=1, padding=(0, 8), align="center")[text(f"Fila {i}")]

    n = Signal(count)
    view = lambda: column()[virtual_list(n(), item, item_height=20, key=key, **kw)]
    pilot = App(view, size=size).pilot()
    pilot.settle()
    return pilot, built, n


def test_builds_only_the_visible_rows():
    pilot, built, _ = _list()
    # Hasta medir la zona visible se supone un alto de pantalla; después, 200 px / 20 px por
    # fila + overscan. En ningún momento se construyen las 10 000.
    assert max(built) < 100
    assert pilot.rect("lista#20") is None
    assert pilot.rect("lista#0") == (0, 0, 300, 20)
    assert pilot.rect("lista#9") is not None
    assert pilot.rect("lista#500") is None


def test_scrolling_moves_the_visible_range():
    pilot, built, _ = _list()
    pilot.scroll("lista", dy=5000)
    pilot.settle()
    assert pilot.scroll_offset("lista") == (0, 5000)
    assert pilot.rect("lista#0") is None
    _, y, _, h = pilot.rect("lista#250")
    assert (y, h) == (0, 20)  # 250 * 20 = 5000: justo arriba de la zona visible
    assert pilot.rect("lista#259") is not None
    assert len([i for i in built if i >= 240]) < 40


def test_content_has_the_height_of_every_row():
    pilot, _, _ = _list(1000, gap=4)
    pilot.scroll("lista", dy=1_000_000)
    pilot.settle()
    total = 1000 * 20 + 999 * 4
    assert pilot.scroll_offset("lista") == (0, total - 200)
    assert pilot.rect("lista#999")[1] + 20 == pytest.approx(200)


def test_shrinking_the_count_clamps_the_range():
    pilot, _, n = _list(1000)
    pilot.scroll("lista", dy=10_000)
    pilot.settle()
    n.set(5)
    pilot.settle()
    assert pilot.scroll_offset("lista") == (0, 0)
    assert pilot.rect("lista#4") is not None
    assert pilot.rect("lista#5") is None


def test_memoized_rows_are_not_rebuilt_while_visible():
    calls = []

    @component
    def item(i: int):
        calls.append(i)
        return row(grow=1)[text(f"Fila {i}")]

    view = lambda: column()[virtual_list(10_000, item, item_height=20, key="memo", overscan=2)]
    pilot = App(view, size=(300, 200)).pilot()
    pilot.settle()
    before = len(calls)
    pilot.scroll("memo", dy=60)  # 3 filas: entran 3 nuevas
    pilot.settle()
    assert len(calls) - before == 3


def test_rejects_non_positive_item_height():
    with pytest.raises(ValueError, match="item_height"):
        App(lambda: virtual_list(10, lambda i: text(str(i)), item_height=0, key="x")).pilot()


def test_on_scroll_reports_changes_without_rebuilding():
    events = []
    view = lambda: column()[
        scroll(key="s", height=100, on_scroll=events.append)[
            [text(f"línea {i}", key=f"l{i}") for i in range(50)]
        ]
    ]
    pilot = App(view, size=(200, 200)).pilot()
    # Primer frame: se conoce la zona visible.
    assert [(e.y, e.height) for e in events] == [(0, 100)]
    pilot.frame()
    assert len(events) == 1  # sin cambios, sin aviso

    pilot.scroll("s", dy=40)
    assert (events[-1].x, events[-1].y, events[-1].height) == (0, 40, 100)
    assert events[-1].width == 200
    pilot.frame()
    assert pilot.stats["rebuilt"] is False  # avisar no reconstruye la vista


def test_jumps_show_their_rows_in_the_same_frame():
    # Un salto mayor que el margen de filas de más: la lista se reconstruye y repinta antes de
    # terminar el frame, sin dejar huecos visibles.
    pilot, _, _ = _list()
    pilot.scroll("lista", dy=50_000)
    assert pilot.rect("lista#2500") is not None
    assert pilot.rect("lista#2509") is not None
