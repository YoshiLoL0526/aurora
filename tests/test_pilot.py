"""Tests de interacción con el piloto headless: mismo runtime que la ventana, sin pantalla."""

import asyncio
import threading

import pytest
from test_render import _png_pixel

from aurora import MIDNIGHT, App, Signal, _core, box, button, column, row, text


def test_click_runs_handler_and_rebuilds():
    count = Signal(0)

    def view():
        # El ancho refleja el estado: así se ve si la vista se reconstruyó.
        return column()[
            button("Sumar", lambda: count.update(lambda n: n + 1), key="add"),
            box(key="bar", width=10 + count() * 10, height=4),
        ]

    pilot = App(view, size=(200, 100)).pilot()
    assert pilot.rect("bar")[2] == 10
    pilot.click("add")
    pilot.click("add")
    assert count() == 2
    assert pilot.rect("bar")[2] == 30


def test_click_on_child_bubbles_to_interactive_ancestor():
    clicks = []
    view = lambda: column()[box(key="btn", on_click=lambda: clicks.append("btn"))[text("OK", key="label")]]
    pilot = App(view, size=(200, 100)).pilot()
    pilot.click("label")
    assert clicks == ["btn"]


def test_capture_stops_bubbling():
    clicks = []
    view = lambda: box(key="backdrop", on_click=lambda: clicks.append("fuera"))[
        box(key="modal", capture=True, width=50, height=50)
    ]
    pilot = App(view, size=(200, 100)).pilot()
    pilot.click("modal")
    assert clicks == []
    pilot.click_at(150, 80)
    assert clicks == ["fuera"]


def test_release_outside_pressed_node_does_not_click():
    clicks = []
    target = box(key="a", width=50, height=50, on_click=lambda: clicks.append("a"))
    view = lambda: row()[target, box(width=50)]
    pilot = App(view, size=(200, 100)).pilot()
    pilot.move_to(25, 25)
    pilot.mouse_down()
    pilot.move_to(75, 25)
    pilot.mouse_up()
    assert clicks == []


def test_hover_tracks_pointer_and_updates_after_rebuild():
    open_ = Signal(False)

    def view():
        return box(key="root")[
            box(key="toggle", width=40, height=40, on_click=lambda: open_.set(True)),
            open_()
            and box(
                key="sheet",
                position="absolute",
                left=0,
                top=0,
                width=100,
                height=100,
                on_click=lambda: None,
            ),
        ]

    pilot = App(view, size=(200, 200)).pilot()
    pilot.move_to(20, 20)
    assert pilot.hovered == "toggle"
    pilot.click("toggle")
    # El puntero no se movió, pero ahora hay otro nodo debajo.
    assert pilot.hovered == "sheet"
    pilot.leave()
    assert pilot.hovered is None


def test_click_unknown_key_raises():
    pilot = App(lambda: box(), size=(50, 50)).pilot()
    with pytest.raises(LookupError, match="nope"):
        pilot.click("nope")


def test_handler_exception_propagates_and_view_still_rebuilds():
    state = Signal(0)

    def boom():
        state.set(1)
        raise RuntimeError("fallo del usuario")

    view = lambda: column()[box(key="b", width=20, height=20, on_click=boom), box(key="w", width=1 + state())]
    pilot = App(view, size=(100, 100)).pilot()
    with pytest.raises(RuntimeError, match="fallo del usuario"):
        pilot.click("b")
    assert pilot.rect("w")[2] == 2


def test_broken_view_raises_and_keeps_previous_tree():
    broken = Signal(False)

    def view():
        if broken():
            raise ValueError("vista rota")
        return box(key="ok", on_click=lambda: broken.set(True))

    pilot = App(view, size=(50, 50)).pilot()
    pilot.move_to(10, 10)
    pilot.mouse_down()
    with pytest.raises(ValueError, match="vista rota"):
        pilot.mouse_up()
    assert pilot.rect("ok") is not None


def test_settle_runs_transitions_to_rest(tmp_path):
    view = lambda: box(key="b", bg="#000000", bg_hover="#FF0000", on_click=lambda: None)
    pilot = App(view, size=(20, 20)).pilot()
    pilot.move_to(10, 10)
    pilot.settle()
    assert pilot.frame() is False
    out = tmp_path / "hover.png"
    pilot.png(str(out))
    assert _png_pixel(out, 10, 10) == (255, 0, 0)


def test_resize_relayouts():
    pilot = App(lambda: box(key="root"), size=(100, 50)).pilot()
    pilot.resize(300, 80)
    assert pilot.rect("root") == (0, 0, 300, 80)


def test_invalid_pilot_size_raises():
    with pytest.raises(ValueError, match="positivos"):
        App(lambda: box(), size=(0, 10)).pilot()


# --- Capas -----------------------------------------------------------------


def _overlay_view(clicks):
    # La capa superior se declara ANTES que el panel que la taparía en orden normal.
    return box(bg="#000000")[
        box(
            key="menu",
            layer="overlay",
            position="absolute",
            left=0,
            top=0,
            width=60,
            height=60,
            bg="#FF0000",
            on_click=lambda: clicks.append("menu"),
        ),
        box(
            key="panel",
            position="absolute",
            left=0,
            top=0,
            width=100,
            height=100,
            bg="#0000FF",
            on_click=lambda: clicks.append("panel"),
        ),
    ]


def test_overlay_paints_above_later_siblings(tmp_path):
    out = tmp_path / "overlay.png"
    _core.render_png(_overlay_view([]).to_spec(MIDNIGHT), 100, 100, str(out), 1.0)
    assert _png_pixel(out, 30, 30) == (255, 0, 0)
    assert _png_pixel(out, 80, 80) == (0, 0, 255)


def test_overlay_receives_clicks_above_later_siblings():
    clicks = []
    pilot = App(lambda: _overlay_view(clicks), size=(100, 100)).pilot()
    pilot.click_at(30, 30)
    pilot.click_at(80, 80)
    assert clicks == ["menu", "panel"]


def test_overlay_click_bubbles_to_tree_parent():
    clicks = []
    view = lambda: box(key="card", on_click=lambda: clicks.append("card"))[
        box(key="tip", layer="overlay", width=20, height=20)
    ]
    pilot = App(view, size=(100, 100)).pilot()
    pilot.click("tip")
    assert clicks == ["card"]


def test_invalid_layer_raises(tmp_path):
    with pytest.raises(ValueError, match="layer"):
        _core.render_png(box(layer="top").to_spec(MIDNIGHT), 10, 10, str(tmp_path / "x.png"), 1.0)


def test_non_callable_handler_raises(tmp_path):
    with pytest.raises(ValueError, match="on_click"):
        _core.render_png(box(on_click="no").to_spec(MIDNIGHT), 10, 10, str(tmp_path / "x.png"), 1.0)


# --- Despertar desde otros hilos ------------------------------------------


def _counting_app(signal):
    builds = []

    def view():
        builds.append(signal())
        return box()

    return App(view, size=(50, 50)), builds


def test_signal_set_from_thread_triggers_rebuild():
    value = Signal(0)
    app, builds = _counting_app(value)
    pilot = app.pilot()
    pilot.frame()
    assert builds == [0]  # sin cambios no se reconstruye

    worker = threading.Thread(target=lambda: value.set(7))
    worker.start()
    worker.join()
    pilot.frame()
    assert builds == [0, 7]


def test_spawn_runs_coroutine_in_background():
    value = Signal("cargando")
    app, builds = _counting_app(value)
    pilot = app.pilot()

    async def load():
        await asyncio.sleep(0)
        value.set("listo")
        return 42

    assert app.spawn(load()).result(timeout=5) == 42
    pilot.frame()
    assert builds[-1] == "listo"


def test_wake_without_event_loop_is_harmless():
    _core.wake()


def test_stats_report_phases_of_last_frame():
    count = Signal(0)
    view = lambda: column()[text(f"n = {count()}"), box(key="a", width=20, height=20)]
    pilot = App(view, size=(200, 100)).pilot()
    stats = pilot.stats
    assert stats["rebuilt"] is True
    assert stats["nodes"] == 3
    assert all(stats[p] >= 0 for p in ("build", "parse", "layout", "paint"))

    # Sin cambios no se reconstruye: build y parse a cero, layout y pintura siguen.
    pilot.frame()
    assert pilot.stats["rebuilt"] is False
    assert pilot.stats["build"] == pilot.stats["parse"] == 0

    count.set(1)
    pilot.frame()
    assert pilot.stats["rebuilt"] is True
