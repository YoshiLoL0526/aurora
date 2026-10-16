"""Inspector del árbol y profiler de frames, con el piloto headless."""

import pytest

from aurora import App, Signal, _core, box, button, column, row, text
from aurora.inspector import PANEL_KEY, enabled, outline


def make_app(clicks: Signal[int] | None = None) -> App:
    counter = clicks if clicks is not None else Signal(0)

    def view():
        return column(key="root", padding=10, gap=8)[
            text("Título", key="title"),
            row(gap=4, key="actions")[
                button("Sumar", lambda: counter.update(lambda n: n + 1), key="add"),
                box(key="swatch", width=40, height=20, padding=4, bg="#FF0000"),
            ],
            text(lambda: f"{counter()} clics", key="count"),
        ]

    return App(view, size=(900, 500))


def test_disabled_by_default():
    pilot = make_app().pilot()
    pilot.press("f12")
    assert pilot.inspection is None
    assert pilot.rect(PANEL_KEY) is None


def test_environment_variable_enables_it(monkeypatch):
    monkeypatch.setenv("AURORA_INSPECTOR", "1")
    assert enabled(None) is True
    assert enabled(False) is False
    monkeypatch.setenv("AURORA_INSPECTOR", "0")
    assert enabled(None) is False
    assert enabled(True) is True


def test_outside_an_app_there_is_nothing_to_inspect():
    assert _core.inspection() is None
    with pytest.raises(RuntimeError):
        _core.inspect_open(True)


def test_f12_docks_the_panel_and_closes_it():
    pilot = make_app().pilot(inspector=True)
    assert pilot.rect("root")[2] == 900
    pilot.press("f12")
    assert pilot.inspection["open"]
    x, _, w, h = pilot.rect(PANEL_KEY)
    assert x + w == 900 and h == 500
    # La app ocupa el resto, sin quedar debajo del panel.
    assert pilot.rect("root")[2] <= x
    pilot.press("f12")
    assert not pilot.inspection["open"]
    assert pilot.rect(PANEL_KEY) is None
    assert pilot.rect("root")[2] == 900


def test_pick_mode_highlights_and_selects_without_reaching_the_app():
    clicks = Signal(0)
    pilot = make_app(clicks).pilot(inspector=True)
    pilot.press("ctrl+shift+c")
    info = pilot.inspection
    assert info["open"] and info["pick"]
    x, y, w, h = pilot.rect("add")
    pilot.move_to(x + w / 2, y + h / 2)
    # Sobre el botón queda su texto, que es lo pintado más arriba.
    assert pilot.inspection["hovered"] == "add/0"
    assert pilot.cursor == "crosshair"
    assert pilot.hovered is None
    pilot.mouse_down()
    pilot.mouse_up()
    assert clicks() == 0
    info = pilot.inspection
    assert info["selected"] == "add/0"
    assert not info["pick"]
    assert info["rect"] is not None
    # Fuera del modo selección, la app vuelve a recibir los clics.
    pilot.click("add")
    assert clicks() == 1


def test_escape_leaves_pick_mode():
    pilot = make_app().pilot(inspector=True)
    pilot.press("ctrl+shift+c")
    pilot.press("escape")
    info = pilot.inspection
    assert info["open"] and not info["pick"]


def test_the_panel_itself_cannot_be_picked():
    pilot = make_app().pilot(inspector=True)
    pilot.press("ctrl+shift+c")
    x, y, w, h = pilot.rect(PANEL_KEY)
    pilot.move_to(x + w / 2, y + h / 2)
    assert pilot.inspection["hovered"] is None
    # El botón del panel sigue funcionando: sale del modo selección.
    pilot.click("aurora:inspector-pick")
    assert not pilot.inspection["pick"]


def test_clicking_a_tree_row_selects_the_node():
    pilot = make_app().pilot(inspector=True, size=(900, 700))
    pilot.press("f12")
    # Filas: root, title, actions, add, add/0, swatch, count.
    pilot.click("aurora:inspector-tree#5")
    info = pilot.inspection
    assert info["selected"] == "swatch"
    assert info["rect"] == pilot.rect("swatch")


def test_collapsing_a_branch_hides_its_rows():
    pilot = make_app().pilot(inspector=True, size=(900, 700))
    pilot.press("f12")
    assert pilot.rect("aurora:inspector-tree#6") is not None
    # La fila 2 es `actions`; su flecha pliega sus tres descendientes y
    # quedan root, title, actions y count.
    x, y, _, h = pilot.rect("aurora:inspector-tree#2")
    pilot.click_at(x + 6 + 12 + 7, y + h / 2)
    assert pilot.rect("aurora:inspector-tree#3") is not None
    assert pilot.rect("aurora:inspector-tree#4") is None
    assert pilot.inspection["selected"] is None


def test_outline_keys_match_the_core():
    pilot = make_app().pilot(inspector=True)
    pilot.press("f12")
    app = make_app()
    spec = app._build()
    for node in outline(spec, "0"):
        assert pilot.rect(node.key) is not None, node.key


def test_frames_are_recorded_and_the_panel_refreshes_by_itself(monkeypatch):
    from aurora import inspector

    shown: list[int] = []
    original = inspector.Inspector.frames

    def spy(self, frames):
        shown.append(len(frames))
        return original(self, frames)

    monkeypatch.setattr(inspector.Inspector, "frames", spy)
    pilot = make_app().pilot(inspector=True)
    pilot.press("f12")
    pilot.click("aurora:inspector-tabs-frames")
    last = pilot.inspection["frames"][-1]
    phases = ("build", "parse", "style", "layout", "draw", "paint")
    assert last["total"] == pytest.approx(sum(last[p] for p in phases))
    # El panel se construyó antes de que terminara el frame del clic. Sin más
    # eventos, se refresca solo con los frames nuevos a los 250 ms…
    before = shown[-1]
    pilot.settle()
    for _ in range(30):
        pilot.frame()
    assert shown[-1] > before
    # …y los refrescos no cuentan como frames ni piden otro.
    count = len(pilot.inspection["frames"])
    builds = len(shown)
    for _ in range(60):
        pilot.frame()
    assert len(pilot.inspection["frames"]) == count
    assert len(shown) == builds
