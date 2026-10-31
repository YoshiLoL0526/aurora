"""`virtual_list` y `on_scroll`: solo se construye lo visible y se sigue al desplazamiento."""

from itertools import pairwise

import pytest

from aurora import App, Signal, box, column, component, row, scroll, text, virtual_list


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


# --- Alto variable (sin `item_height`) ---


def _alto(i: int) -> int:
    return 20 + (i * 37) % 60


def _variable(count=5000, *, key, size=(300, 400), **kw):
    built = []

    def item(i: int):
        built.append(i)
        return box(height=_alto(i))[text(str(i))]

    n = Signal(count)
    view = lambda: column()[virtual_list(n(), item, key=key, **kw)]
    pilot = App(view, size=size).pilot()
    pilot.settle()
    return pilot, built, n


def _primera_visible(pilot, key, count):
    for i in range(count):
        r = pilot.rect(f"{key}#{i}")
        if r is not None and r[1] >= 0:
            return i, r[1]
    raise AssertionError("ninguna fila visible")


def test_variable_rows_take_their_measured_height():
    pilot, built, _ = _variable(key="var-alto", gap=2)
    assert max(built) < 100  # sigue sin construir las 5000
    rows = [(i, pilot.rect(f"var-alto#{i}")) for i in range(30)]
    rows = [(i, r) for i, r in rows if r is not None]
    assert len(rows) > 5
    for (i, a), (_, b) in pairwise(rows):
        assert a[3] == _alto(i)  # el hueco mide lo que pide la fila
        assert a[1] + a[3] + 2 == pytest.approx(b[1])  # sin solaparse ni dejar huecos


def test_measuring_rows_above_does_not_move_what_is_visible():
    # Muy abajo, las filas de encima se suponen de 40 px. Al subir, entran y se miden (miden
    # entre 20 y 80): el alto total cambia, pero lo que se estaba viendo no salta.
    pilot, _, _ = _variable(key="var-ancla", gap=2)
    pilot.scroll("var-ancla", dy=100_000)
    pilot.settle()
    i, y = _primera_visible(pilot, "var-ancla", 5000)
    for step in range(1, 6):
        pilot.scroll("var-ancla", dy=-50)
        pilot.settle()
        assert pilot.rect(f"var-ancla#{i}")[1] == pytest.approx(y + 50 * step)


def test_scrolling_to_the_end_shows_the_last_row():
    # Las últimas filas miden más de lo estimado: al medirse, la lista sigue mostrando el final.
    pilot, _, _ = _variable(key="var-final")
    pilot.scroll("var-final", dy=10_000_000)
    pilot.settle()
    _, y, _, h = pilot.rect("var-final#4999")
    assert y + h == pytest.approx(400)


def test_stick_to_end_follows_new_rows_only_while_at_the_end():
    pilot, _, n = _variable(3, key="var-chat", size=(300, 200), stick_to_end=True)
    for count in (5, 12, 40):
        n.set(count)
        pilot.settle()
        _, y, _, h = pilot.rect(f"var-chat#{count - 1}")
        assert y + h == pytest.approx(200)  # la última, pegada abajo
    pilot.scroll("var-chat", dy=-100)
    pilot.settle()
    before = pilot.scroll_offset("var-chat")
    n.set(41)
    pilot.settle()
    assert pilot.scroll_offset("var-chat") == before  # leyendo más arriba: no se mueve
    assert pilot.rect("var-chat#40")[1] >= 200  # la nueva queda por debajo, sin verse


def test_stick_to_end_with_fixed_height_starts_at_the_end():
    pilot, _, n = _list(100, key="fija-chat", stick_to_end=True)
    assert pilot.scroll_offset("fija-chat") == (0, 100 * 20 - 200)
    n.set(101)
    pilot.settle()
    assert pilot.rect("fija-chat#100") == (0, 180, 300, 20)


def test_scroll_anchor_keeps_the_visible_content_still():
    # `scroll_anchor` también vale para un `scroll` cualquiera: cargar contenido arriba no
    # empuja lo que se lee.
    above = Signal(0)
    view = lambda: column()[
        scroll(key="ancla", height=100, scroll_anchor=True)[
            [box(key=f"extra{i}", height=30) for i in range(above())],
            [text(f"línea {i}", key=f"l{i}") for i in range(30)],
        ]
    ]
    pilot = App(view, size=(200, 200)).pilot()
    pilot.scroll("ancla", dy=120)
    pilot.settle()
    y = pilot.rect("l10")[1]
    above.set(3)
    pilot.settle()
    assert pilot.scroll_offset("ancla") == (0, 210)
    assert pilot.rect("l10")[1] == y


def test_rejects_non_positive_estimated_height():
    with pytest.raises(ValueError, match="estimated_height"):
        App(lambda: virtual_list(10, lambda i: text(str(i)), estimated_height=0, key="x")).pilot()
