"""Tests de interacción con el piloto headless: mismo runtime que la ventana, sin pantalla."""

import asyncio
import threading
from datetime import date

import pytest
from test_render import _png_pixel

from aurora import (
    MIDNIGHT,
    App,
    Signal,
    _core,
    box,
    button,
    column,
    date_picker,
    popover,
    row,
    scroll,
    spacer,
    splitter,
    text,
    tree,
)


@pytest.fixture(autouse=True)
def _fresh_component_state():
    """Cada test empieza sin el estado por key de los componentes (desplegables, splitters…)."""
    from aurora.components import _state

    for name, store in vars(_state).items():
        if not name.startswith("__") and isinstance(store, dict):
            store.clear()


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


def test_drag_reports_phases_and_offset_from_the_press():
    events = []
    clicks = []
    view = lambda: column()[
        box(key="handle", width=40, height=40, on_drag=events.append, on_click=lambda: clicks.append(1))
    ]
    pilot = App(view, size=(200, 100)).pilot()
    pilot.drag("handle", dx=30, dy=-10, steps=3)
    assert [e.phase for e in events] == ["start", "move", "move", "move", "end"]
    assert (events[0].x, events[0].y, events[0].dx) == (20, 20, 0)
    assert (events[-1].dx, events[-1].dy) == (30, -10)
    assert (events[-1].x, events[-1].y) == (50, 10)
    # Un arrastre que se movió no es un clic; pulsar y soltar sin moverse, sí.
    assert clicks == []
    pilot.click("handle")
    assert clicks == [1]
    assert [e.phase for e in events[-2:]] == ["start", "end"]


def test_drag_keeps_reporting_outside_the_node():
    width = Signal(40.0)
    start = {}

    def resize(e):
        if e.phase == "start":
            start["w"] = width()
        width.set(max(10.0, start["w"] + e.dx))

    view = lambda: row()[
        box(key="panel", width=width(), height=40),
        box(key="grip", width=6, height=40, cursor="col-resize", on_drag=resize),
    ]
    pilot = App(view, size=(300, 100)).pilot()
    pilot.drag("grip", dx=120, steps=6)
    assert pilot.rect("panel") == (0, 0, 160, 40)
    assert pilot.rect("grip")[0] == 160


def test_drag_is_not_focusable_and_does_not_steal_focus():
    view = lambda: column()[
        button("OK", lambda: None, key="ok"),
        box(key="grip", width=20, height=20, on_drag=lambda e: None),
    ]
    pilot = App(view, size=(200, 100)).pilot()
    pilot.focus("ok")
    pilot.drag("grip", dx=10)
    assert pilot.focused == "ok"
    pilot.press("tab")
    assert pilot.focused == "ok"  # el único enfocable


def test_cursor_style_applies_to_children_and_during_drag():
    view = lambda: row()[
        box(key="area", width=60, height=40, cursor="col-resize")[box(key="inner", width=20, height=20)],
        box(key="link", width=60, height=40, on_click=lambda: None),
        box(key="grip", width=10, height=40, cursor="row-resize", on_drag=lambda e: None),
    ]
    pilot = App(view, size=(300, 100)).pilot()
    pilot.move_to(5, 5)  # sobre `inner`: hereda el cursor de `area`
    assert pilot.cursor == "col-resize"
    pilot.move_to(90, 20)
    assert pilot.cursor == "pointer"
    pilot.move_to(250, 20)
    assert pilot.cursor == "default"
    pilot.move_to(125, 20)
    pilot.mouse_down()
    pilot.move_to(250, 20)  # fuera del nodo: el arrastre conserva su cursor
    assert pilot.cursor == "row-resize"
    pilot.mouse_up()
    assert pilot.cursor == "default"


def test_overflow_hidden_clips_clicks_and_toggles():
    hits = []
    clipped = Signal(True)

    def view():
        return column()[
            box(width=100, height=20, overflow="hidden" if clipped() else "visible")[
                # Sin encogerse: desborda y el recorte es lo que lo oculta.
                box(width=100, height=60, shrink=0, bg="#222222", on_click=lambda: hits.append(1))
            ],
            box(key="below", width=100, height=20, on_click=lambda: hits.append(2)),
        ]

    pilot = App(view, size=(120, 80)).pilot()
    pilot.click_at(50, 30)  # sobre el recorte: gana el hermano pintado después
    assert hits == [2]
    pilot.click_at(50, 50)  # solo lo cubre el contenido desbordado
    assert hits == [2]
    clipped.set(False)
    pilot.settle()
    pilot.click_at(50, 50)
    assert hits == [2, 1]  # sin recorte sí lo recibe


def test_invalid_cursor_raises(tmp_path):
    with pytest.raises(ValueError, match="cursor"):
        App(lambda: box(cursor="mano"), size=(10, 10)).render_png(str(tmp_path / "x.png"))


def test_drop_files_goes_to_drop_zone_under_point(tmp_path):
    got = []
    view = lambda: row(gap=10)[
        box(key="a", width=80, height=80, on_drop=lambda files: got.append(("a", files))),
        box(key="b", width=80, height=80, on_drop=lambda files: got.append(("b", files)))[
            text("Suelta", key="label")
        ],
        box(key="nada", width=80, height=80),
    ]
    pilot = App(view, size=(300, 100)).pilot()
    path = tmp_path / "datos.csv"
    # Burbujea desde el hijo hasta el primer ancestro con `on_drop`; acepta `Path`.
    assert pilot.drop_files([path, "otro.txt"], key="label") is True
    assert got == [("b", [str(path), "otro.txt"])]
    # Fuera de toda zona con `on_drop` no lo recibe nadie.
    assert pilot.drop_files(["x"], key="nada") is False
    assert len(got) == 1


def test_drop_files_without_position_goes_to_first_drop_zone():
    got = []
    view = lambda: column()[
        text("Sin zona"),
        box(key="primera", on_drop=lambda files: got.append(("primera", files))),
        box(key="segunda", on_drop=lambda files: got.append(("segunda", files))),
    ]
    pilot = App(view, size=(200, 100)).pilot()
    # macOS y Linux no dan la posición al soltar: decide el orden del árbol.
    assert pilot.drop_files(["a.png"]) is True
    assert got == [("primera", ["a.png"])]


def test_drop_hover_notifies_every_listener_and_rebuilds():
    hovering = Signal[list[str] | None](None)
    seen = []

    def view():
        return column()[
            box(key="zona", on_drop_hover=hovering.set, on_drop=lambda files: None),
            box(key="otra", on_drop_hover=seen.append),
            text(lambda: f"{len(hovering() or [])} archivos", key="estado"),
        ]

    pilot = App(view, size=(200, 100)).pilot()
    pilot.hover_files(["a.png", "b.png"])
    assert hovering() == ["a.png", "b.png"]
    assert seen == [["a.png", "b.png"]]
    # Soltar termina el arrastre: los avisos reciben `None`.
    pilot.drop_files(["a.png", "b.png"], key="zona")
    assert hovering() is None
    assert seen == [["a.png", "b.png"], None]
    # Salir sin soltar también; un segundo `None` no vuelve a avisar.
    pilot.hover_files(["c.txt"])
    pilot.hover_files(None)
    pilot.hover_files(None)
    assert seen[-2:] == [["c.txt"], None]
    assert len(seen) == 4


def test_drop_handler_error_surfaces():
    def boom(files):
        raise RuntimeError("fallo al soltar")

    pilot = App(lambda: box(key="z", width=50, height=50, on_drop=boom), size=(100, 100)).pilot()
    with pytest.raises(RuntimeError, match="fallo al soltar"):
        pilot.drop_files(["a"], key="z")


# --- popover ----------------------------------------------------------------------


def _popover_app(open_, *, bottom=False, **kwargs):
    def view():
        pop = popover(
            button("Abrir", key="btn"), text("Contenido", key="body"), open=open_, key="pop", **kwargs
        )
        return column(padding=10)[spacer() if bottom else None, row()[pop]]

    return App(view, size=(400, 300)).pilot()


def test_popover_opens_below_and_closes_with_escape_or_outside_click():
    open_, closed = Signal(False), []
    pilot = _popover_app(open_, label="Detalles", on_close=lambda: closed.append(True))
    assert pilot.rect("pop-panel") is None
    pilot.click("btn")
    assert open_()
    bx, by, _, bh = pilot.rect("btn")
    px, py, *_ = pilot.rect("pop-panel")
    assert (px, py) == (bx, by + bh + 6)
    nodes = {n["key"]: n for n in pilot.a11y_tree()}
    assert nodes["pop-panel"]["role"] == "dialog"
    assert nodes["pop-panel"]["label"] == "Detalles"
    assert nodes["btn"]["expanded"] is True
    pilot.press("escape")
    assert not open_() and closed == [True]
    pilot.click("btn")
    pilot.click_at(380, 280)  # fuera del panel
    assert not open_() and closed == [True, True]
    pilot.click("btn")
    pilot.click("btn")  # el disparador también lo cierra
    assert not open_()


def test_popover_flips_above_when_there_is_no_room_below():
    pilot = _popover_app(Signal(True), bottom=True)
    _, by, _, _ = pilot.rect("btn")
    _, py, _, ph = pilot.rect("pop-panel")
    assert py + ph == by - 6


def test_popover_side_placement_stays_inside_the_window():
    pilot = _popover_app(Signal(True), placement="right-center", width=380)
    x, _, w, _ = pilot.rect("pop-panel")
    assert x >= 8 and x + w <= 400 - 8


def test_popover_needs_a_key_or_a_signal():
    with pytest.raises(ValueError, match="popover"):
        popover(button("x"), text("y"))


def test_invalid_placement_is_a_clear_error():
    view = lambda: column()[box(layer="overlay", position="absolute", placement="debajo")]
    with pytest.raises(ValueError, match="placement"):
        App(view, size=(100, 100)).pilot()


def test_dropdown_panels_flip_near_the_bottom_edge():
    view = lambda: column(padding=10)[spacer(), date_picker(Signal(date(2026, 3, 10)), key="dp")]
    pilot = App(view, size=(360, 460)).pilot()
    pilot.click("dp")
    _, ty, _, _ = pilot.rect("dp")
    _, dy, _, _ = pilot.rect("dp-day-2026-03-10")
    assert dy < ty  # el calendario se abre hacia arriba


def test_popover_anchors_to_the_trigger_even_in_a_stretched_wrapper():
    def view():
        pop = popover(button("Abrir", key="btn"), text("Hola"), open=Signal(True), key="pop")
        return row(padding=20, height=300)[pop]  # la fila estira al envoltorio en vertical

    pilot = App(view, size=(400, 300)).pilot()
    _, by, _, bh = pilot.rect("btn")
    assert pilot.rect("pop")[3] > bh
    assert pilot.rect("pop-panel")[1] == by + bh + 6


# --- splitter ---------------------------------------------------------------------


def _split_app(size, **kwargs):
    view = lambda: column()[splitter(scroll()[text("A")], scroll()[text("B")], size=size, key="s", **kwargs)]
    return App(view, size=(500, 300)).pilot()


def test_splitter_drag_resizes_and_respects_both_minimums():
    size, seen = Signal(150.0), []
    pilot = _split_app(size, min_sizes=(100, 120), on_change=seen.append)
    assert pilot.rect("s-first")[2] == 150
    pilot.drag("s-handle", 80)
    assert size() == 230
    assert pilot.rect("s-first")[2] == 230
    assert pilot.rect("s-second")[0] == 237  # tras la franja de 7 px
    pilot.drag("s-handle", 1000)
    assert size() == 500 - 7 - 120
    pilot.drag("s-handle", -1000)
    assert size() == 100
    assert seen[-1] == 100


def test_splitter_keyboard_and_screen_reader_actions():
    size = Signal(200.0)
    pilot = _split_app(size, step=10)
    pilot.focus("s-handle")
    pilot.press("right")
    assert size() == 210
    pilot.press("left")
    pilot.press("left")
    assert size() == 190
    pilot.press("end")
    assert size() == 500 - 7 - 80
    pilot.press("home")
    assert size() == 80
    pilot.a11y_action("s-handle", "increment")
    assert size() == 90
    pilot.a11y_action("s-handle", "set_value", 300.0)
    assert size() == 300
    node = next(n for n in pilot.a11y_tree() if n["key"] == "s-handle")
    assert node["role"] == "separator"
    assert node["orientation"] == "vertical"
    assert node["numeric_value"] == 300


def test_splitter_column_direction_uses_vertical_keys_and_drag():
    size = Signal(100.0)
    pilot = _split_app(size, direction="column")
    assert pilot.rect("s-first")[3] == 100
    pilot.drag("s-handle", 0, 40)
    assert size() == 140
    pilot.focus("s-handle")
    pilot.press("up")
    assert size() == 124
    assert next(n for n in pilot.a11y_tree() if n["key"] == "s-handle")["orientation"] == "horizontal"


def test_splitter_without_signal_keeps_its_size_by_key():
    pilot = App(
        lambda: column()[splitter(text("A"), text("B"), size=180, key="libre")], size=(500, 300)
    ).pilot()
    pilot.drag("libre-handle", 20)
    assert pilot.rect("libre-first")[2] == 200
    with pytest.raises(ValueError, match="key"):
        splitter(text("A"), text("B"), size=100)
    with pytest.raises(ValueError, match="direction"):
        splitter(text("A"), text("B"), size=Signal(1.0), direction="diagonal")  # ty: ignore[invalid-argument-type]


def test_splitter_first_pane_yields_when_the_window_shrinks():
    size = Signal(400.0)
    pilot = _split_app(size, min_sizes=(100, 150))
    # 500 - 7 - 150: el primer panel cede para respetar el mínimo del segundo.
    assert pilot.rect("s-first")[2] == 343
    assert size() == 400


def test_on_resize_reports_the_laid_out_size():
    sizes = []
    view = lambda: row(padding=10)[
        box(key="b", grow=1, height=30, on_resize=lambda e: sizes.append((e.width, e.height)))
    ]
    pilot = App(view, size=(200, 100)).pilot()
    pilot.frame()
    assert sizes == [(180, 30)]


# --- tree -------------------------------------------------------------------------

_FILES = [
    ("src", [("app.py", []), ("ui", [("tree.py", []), ("splitter.py", [])])]),
    ("README.md", []),
    ("tests", [(f"test_{i}.py", []) for i in range(500)]),
]


def _tree_app(**kwargs):
    view = lambda: column(padding=10)[
        tree(_FILES, lambda n: n[1], label=lambda n: n[0], key="t", height=200, **kwargs)
    ]
    return App(view, size=(300, 240)).pilot()


def _items(pilot):
    return [n for n in pilot.a11y_tree() if n["role"] == "treeitem"]


def test_tree_click_selects_and_chevron_expands():
    expanded, selected, seen = Signal(set()), Signal(None), []
    pilot = _tree_app(expanded=expanded, selected=selected, on_select=lambda n: seen.append(n[0]))
    assert [n["key"] for n in _items(pilot)] == ["t-src", "t-README.md", "t-tests"]
    pilot.click("t-README.md")
    assert selected() == ("README.md",) and seen == ["README.md"]
    x, y, _, h = pilot.rect("t-src")
    pilot.click_at(x + 14, y + h / 2)  # el triángulo
    assert expanded() == {("src",)}
    assert selected() == ("README.md",)  # desplegar no cambia la selección
    assert "t-src/app.py" in [n["key"] for n in _items(pilot)]


def test_tree_keyboard_follows_the_treeview_pattern():
    expanded, selected, activated = Signal(set()), Signal(None), []
    pilot = _tree_app(expanded=expanded, selected=selected, on_activate=lambda n: activated.append(n[0]))
    pilot.focus("t")
    pilot.press("down")
    assert selected() == ("src",)
    pilot.press("right")  # despliega
    assert expanded() == {("src",)}
    pilot.press("right")  # baja al primer hijo
    assert selected() == ("src", "app.py")
    pilot.press("down")
    pilot.press("right")
    pilot.press("right")
    assert selected() == ("src", "ui", "tree.py")
    pilot.press("left")  # una hoja sube a su padre
    assert selected() == ("src", "ui")
    pilot.press("left")  # un padre desplegado se pliega
    assert expanded() == {("src",)}
    pilot.press("end")
    assert selected() == ("tests",)
    pilot.press("home")
    assert selected() == ("src",)
    pilot.press("enter")
    assert activated == ["src"]


def test_tree_announces_levels_positions_and_expansion():
    pilot = _tree_app(expanded=Signal({("src",), ("src", "ui")}), selected=Signal(("src", "ui")))
    nodes = {n["key"]: n for n in pilot.a11y_tree()}
    assert nodes["t"]["role"] == "tree"
    ui = nodes["t-src/ui"]
    assert (ui["level"], ui["position_in_set"], ui["set_size"]) == (2, 2, 2)
    assert ui["expanded"] is True and ui["selected"] is True
    leaf = nodes["t-src/ui/splitter.py"]
    assert leaf["level"] == 3 and leaf["expanded"] is None


def test_tree_virtualizes_and_keeps_the_selection_in_view():
    selected = Signal(None)
    pilot = _tree_app(expanded=Signal({("tests",)}), selected=selected)
    assert len(_items(pilot)) < 30  # 503 filas visibles, pocas construidas
    pilot.focus("t")
    pilot.press("down")
    pilot.press("end")
    pilot.settle()
    assert selected() == ("tests", "test_499.py")
    _, y, _, h = pilot.rect("t-tests/test_499.py")
    assert y >= 10 and y + h <= 210


def test_tree_custom_identity_and_state_by_key():
    nodes = {1: [2, 3], 2: [], 3: [4], 4: []}
    names = {1: "raíz", 2: "a", 3: "b", 4: "c"}
    view = lambda: column()[
        tree([1], lambda n: nodes[n], label=lambda n: names[n], ident=lambda n: n, key="k")
    ]
    pilot = App(view, size=(300, 240)).pilot()
    pilot.focus("k")
    pilot.press("down")
    pilot.press("right")
    assert [n["key"] for n in _items(pilot)] == ["k-1", "k-2", "k-3"]


def test_scroll_reveal_scrolls_only_when_the_band_changes():
    band = Signal((0.0, 20.0))
    view = lambda: column()[
        scroll(key="s", height=100, reveal=band())[[box(key=f"b{i}", height=20, shrink=0) for i in range(30)]]
    ]
    pilot = App(view, size=(200, 120)).pilot()
    band.set((400.0, 420.0))
    pilot.frame()
    pilot.settle()
    _, y, _, _ = pilot.rect("b20")
    assert 0 <= y <= 80
