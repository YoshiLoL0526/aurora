"""Reconstrucción parcial: un `Signal` que solo leen regiones (lambdas de textos,
propiedades e hijos) no vuelve a llamar a la vista; se rehacen esas regiones y
el resto del árbol reutiliza su serialización."""

import numpy as np
import pytest

import aurora
from aurora import (
    DAYLIGHT,
    MIDNIGHT,
    App,
    Signal,
    animate,
    box,
    chart,
    column,
    component,
    row,
    scroll,
    text,
    text_input,
)


class Counted:
    """Envuelve una vista y cuenta cuántas veces se llama."""

    def __init__(self, view):
        self.view = view
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.view()


def value(pilot, key):
    """El texto de un nodo, como lo anuncia a los lectores de pantalla."""
    return next(n["value"] for n in pilot.a11y_tree() if n["key"] == key)


@pytest.fixture
def partial(monkeypatch):
    """`app._build()` como lo llama el núcleo cuando no corrió ningún manejador."""
    monkeypatch.setattr(aurora._core, "build_partial", lambda: True)


def find(spec, key):
    if spec["key"] == key:
        return spec
    for child in spec["children"]:
        if (found := find(child, key)) is not None:
            return found
    return None


def test_a_text_lambda_does_not_rerun_the_view():
    n = Signal(0)
    view = Counted(lambda: column()[text(lambda: f"{n()} clics", key="t"), text("fijo", key="f")])
    pilot = App(view).pilot()
    assert view.calls == 1 and value(pilot, "t") == "0 clics"
    for i in range(1, 4):
        n.set(i)
        pilot.frame()
        assert value(pilot, "t") == f"{i} clics"
    assert view.calls == 1


def test_what_the_view_reads_rebuilds_it_whole():
    n = Signal(0)
    view = Counted(lambda: column()[text(f"{n()} directo", key="t")])
    pilot = App(view).pilot()
    n.set(1)
    pilot.frame()
    assert view.calls == 2 and value(pilot, "t") == "1 directo"


def test_only_the_regions_that_read_the_signal_run_again(partial):
    a, b = Signal(0), Signal(0)
    runs = {"a": 0, "b": 0}

    def label(name, signal):
        def read():
            runs[name] += 1
            return f"{name}={signal()}"

        return read

    app = App(
        lambda: column()[
            text(label("a", a), key="a"),
            text(label("b", b), key="b"),
            column(key="lista")[[row(key=f"r{i}")[text(f"fila {i}")] for i in range(50)]],
        ]
    )
    first = app._build()
    lista = find(first, "lista")
    a.set(1)
    second = app._build()
    assert runs == {"a": 2, "b": 1}
    assert find(second, "a")["text"] == "a=1"
    # Lo que no depende de `a` es el mismo dict: ni se recorre ni se vuelve a serializar.
    assert find(second, "lista") is lista and find(second, "b") is find(first, "b")
    assert second is not first


def test_property_lambdas_are_regions(partial):
    on = Signal(False)
    view = Counted(
        lambda: column()[box(key="punto", width=10, height=10, bg=lambda: "$success" if on() else "$danger")]
    )
    app = App(view, theme=DAYLIGHT)
    assert find(app._build(), "punto")["style"]["bg"] == DAYLIGHT.resolve("$danger")
    on.set(True)
    assert find(app._build(), "punto")["style"]["bg"] == DAYLIGHT.resolve("$success")
    assert view.calls == 1


def test_a_lambda_child_is_a_region_in_its_place():
    count = Signal(2)
    inner = Signal("x")
    view = Counted(
        lambda: column(key="col")[
            text("antes", key="antes"),
            lambda: [text(lambda i=i: f"{inner()}{i}", key=f"item-{i}") for i in range(count())],
            text("después", key="despues"),
        ]
    )
    pilot = App(view).pilot()
    keys = [n["key"] for n in pilot.a11y_tree() if n["role"] == "label"]
    assert keys == ["antes", "item-0", "item-1", "despues"]

    count.set(3)
    pilot.frame()
    assert [n["key"] for n in pilot.a11y_tree() if n["role"] == "label"] == [
        "antes",
        "item-0",
        "item-1",
        "item-2",
        "despues",
    ]
    # Las regiones de dentro del hijo calculado son las nuevas: cambian con lo que leen.
    inner.set("y")
    pilot.frame()
    assert value(pilot, "item-2") == "y2"
    count.set(1)
    pilot.frame()
    inner.set("z")
    pilot.frame()
    assert value(pilot, "item-0") == "z0" and pilot.rect("item-1") is None
    assert view.calls == 1


def test_a_signal_can_be_a_child():
    items = Signal([text("uno", key="uno")])
    pilot = App(lambda: column()[items]).pilot()
    assert pilot.rect("uno") is not None
    items.set([text("dos", key="dos")])
    pilot.frame()
    assert pilot.rect("uno") is None and pilot.rect("dos") is not None


def test_plain_python_state_still_rebuilds_the_view():
    """Un evento que no cambia ningún `Signal` (estado normal de Python) reconstruye entera."""
    todos = ["a"]
    n = Signal(0)
    view = Counted(
        lambda: column()[
            text(lambda: f"{n()}", key="n"),
            box(key="add", width=10, height=10, on_click=lambda: todos.append("b")),
            [text(t, key=f"todo-{t}") for t in todos],
        ]
    )
    pilot = App(view).pilot()
    pilot.click("add")
    assert view.calls == 2 and pilot.rect("todo-b") is not None


def test_a_signal_nobody_reads_rebuilds_the_view():
    """Un `Signal` que solo se cambia para forzar una reconstrucción sigue sirviendo."""
    data = ["a"]
    poke = Signal(0)
    view = Counted(lambda: column()[[text(t, key=t) for t in data]])
    pilot = App(view).pilot()
    data.append("b")
    poke.set(1)
    pilot.frame()
    assert view.calls == 2 and pilot.rect("b") is not None


def test_partial_rebuild_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("AURORA_PARTIAL", "0")
    n = Signal(0)
    view = Counted(lambda: column()[text(lambda: f"{n()}", key="t")])
    pilot = App(view).pilot()
    n.set(1)
    pilot.frame()
    assert view.calls == 2 and value(pilot, "t") == "1"


def test_a_component_with_a_text_lambda_is_reused_and_reserialized():
    n = Signal(0)
    built = []

    @component
    def tarjeta(name: str):
        built.append(name)
        return column(key=f"card-{name}")[text(lambda: f"{name}:{n()}", key=f"t-{name}")]

    selected = Signal("a")
    view = Counted(lambda: column()[tarjeta("a"), tarjeta("b"), text(selected(), key="sel")])
    pilot = App(view).pilot()
    n.set(1)
    pilot.frame()
    assert value(pilot, "t-a") == "a:1" and view.calls == 1
    # Al reconstruir la vista entera, el componente no se vuelve a construir:
    # solo cambió lo que lee su texto, y eso ya se reserializó.
    selected.set("b")
    pilot.frame()
    n.set(2)
    pilot.frame()
    assert view.calls == 2 and built == ["a", "b"] and value(pilot, "t-b") == "b:2"


def test_components_created_inside_a_region_follow_it():
    rows = Signal(2)
    built = []

    @component
    def fila(i: int):
        built.append(i)
        return text(f"fila {i}", key=f"fila-{i}")

    view = Counted(lambda: column()[lambda: [fila(i) for i in range(rows())]])
    pilot = App(view).pilot()
    rows.set(3)
    pilot.frame()
    # Las dos primeras filas siguen memorizadas: la región solo construye la nueva.
    assert built == [0, 1, 2] and pilot.rect("fila-2") is not None and view.calls == 1


def test_focus_and_scroll_survive_a_partial_rebuild():
    query = Signal("")
    n = Signal(0)
    view = Counted(
        lambda: column()[
            text_input(query, key="campo"),
            text(lambda: f"{n()}", key="n"),
            scroll(key="lista", height=100)[[text(f"fila {i}", key=f"f{i}") for i in range(100)]],
        ]
    )
    pilot = App(view, size=(300, 300)).pilot()
    pilot.focus("campo")
    pilot.type("ab")
    pilot.scroll("lista", 200)
    pilot.settle()
    offset = pilot.scroll_offset("lista")
    calls = view.calls
    n.set(1)
    pilot.frame()
    assert view.calls == calls
    assert next(x for x in pilot.a11y_tree() if x["key"] == "campo")["focused"]
    assert pilot.scroll_offset("lista") == offset
    pilot.type("c")
    assert query() == "abc"


def test_transitions_animate_a_property_lambda():
    on = Signal(False)
    app = App(
        lambda: column()[
            box(
                key="b",
                width=40,
                height=40,
                opacity=lambda: 1.0 if on() else 0.0,
                transition=animate.tween(0.2),
            ),
            text(lambda: "x" if on() else "y", key="t"),
        ],
        size=(100, 100),
    )
    pilot = app.pilot()
    on.set(True)
    # La transición sigue en marcha unos frames después del cambio.
    assert pilot.frame()
    assert pilot.frame()
    pilot.settle()
    assert not pilot.frame()


def test_two_windows_keep_their_own_regions():
    n = Signal(0)
    view_a = Counted(lambda: column()[text(lambda: f"a{n()}", key="t")])
    view_b = Counted(lambda: column()[text(lambda: f"b{n() * 2}", key="t")])
    app = App(view_a)
    window = app.window(view_b)
    a, b = app.pilot(), window.pilot()
    for i in (1, 2):
        n.set(i)
        a.frame()
        b.frame()
        assert value(a, "t") == f"a{i}" and value(b, "t") == f"b{i * 2}"
    assert view_a.calls == 1 and view_b.calls == 1


def test_theme_change_rebuilds_the_view():
    theme = Signal(MIDNIGHT)
    view = Counted(lambda: column()[box(key="b", width=4, height=4, bg="$primary")])
    app = App(view, theme=theme)
    app._build()
    theme.set(DAYLIGHT)
    assert find(app._build(), "b")["style"]["bg"] == DAYLIGHT.resolve("$primary")
    assert view.calls == 2


def test_a_duplicate_key_from_a_region_is_rejected():
    dup = Signal(False)
    pilot = App(
        lambda: column()[
            text("uno", key="x"),
            column()[lambda: [text("dos", key="x" if dup() else "y")]],
        ]
    ).pilot()
    dup.set(True)
    with pytest.raises(ValueError, match="key duplicada"):
        pilot.frame()
    dup.set(False)
    pilot.frame()
    assert pilot.rect("y") is not None


def test_an_error_in_a_region_recovers_on_the_next_build():
    n = Signal(0)

    def label():
        if n() == 1:
            raise RuntimeError("roto")
        return f"n={n()}"

    view = Counted(lambda: column()[text(label, key="t")])
    pilot = App(view).pilot()
    n.set(1)
    with pytest.raises(RuntimeError, match="roto"):
        pilot.frame()
    n.set(2)
    pilot.frame()
    assert value(pilot, "t") == "n=2"


def test_charts_are_resent_on_every_partial_rebuild():
    """Los datos de un `chart` pueden cambiar en el sitio sin avisar: se reenvían siempre."""
    data = np.zeros(10)
    n = Signal(0)
    app = App(lambda: column()[text(lambda: f"{n()}", key="t"), chart(data, key="c")])
    first = find(app._build(), "c")
    data[:] = 1
    n.set(1)
    assert find(app._build(), "c") is not first


def test_reload_keeps_partial_rebuilds_working(tmp_path, monkeypatch):
    import sys
    import types

    source = (
        "from aurora import App, Signal, column, text\n"
        "n = Signal(0)\n"
        "def view():\n"
        "    return column()[text(lambda: f'{label}{n()}', key='t')]\n"
        "app = App(view)\n"
    )
    path = tmp_path / "app.py"
    path.write_text(source.replace("{label}", "v1:"), encoding="utf-8")
    module = types.ModuleType("aurora_partial_main")
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    monkeypatch.setitem(sys.modules, "aurora_partial_main", module)
    app = module.app
    reloader = app.watch(module)
    pilot = app.pilot()
    module.n.set(1)
    pilot.frame()
    assert value(pilot, "t") == "v1:1"

    import os

    path.write_text(source.replace("{label}", "v2:"), encoding="utf-8")
    stamp = path.stat().st_mtime_ns + 1_000_000_000
    os.utime(path, ns=(stamp, stamp))
    assert reloader.check()
    pilot.frame()
    assert value(pilot, "t") == "v2:1"
    module.n.set(2)
    pilot.frame()
    assert value(pilot, "t") == "v2:2"


def test_the_inspector_docks_over_a_partial_rebuild():
    n = Signal(0)
    view = Counted(lambda: column()[text(lambda: f"{n()}", key="t")])
    pilot = App(view, inspector=True).pilot(inspector=True)
    pilot.press("f12")
    pilot.frame()
    n.set(1)
    pilot.frame()
    assert value(pilot, "t") == "1"


def test_a_handler_that_mixes_plain_state_and_a_signal_rebuilds_the_view():
    """El caso de la vista desactualizada: un clic cambia estado normal que lee `view()`
    y, a la vez, un `Signal` que solo lee una región. La vista tiene que reflejar ambos."""
    todos = ["a"]
    total = Signal(1)

    def add():
        todos.append("b")
        total.set(total() + 1)

    view = Counted(
        lambda: column()[
            text(lambda: f"{total()} tareas", key="total"),
            box(key="add", width=10, height=10, on_click=add),
            text(f"{len(todos)} en la lista", key="len"),
            [text(t, key=f"todo-{t}") for t in todos],
        ]
    )
    pilot = App(view).pilot()
    pilot.click("add")
    assert value(pilot, "total") == "2 tareas"
    assert value(pilot, "len") == "2 en la lista" and pilot.rect("todo-b") is not None
    assert view.calls == 2


def test_typing_and_keys_rebuild_the_view_whole():
    """`on_change` y `on_key` son manejadores de usuario: también reconstruyen entera."""
    log = []
    query = Signal("")

    def change(v):
        log.append(v)
        query.set(v)

    def key(event):
        log.append("tecla")
        query.set(query() + "!")

    view = Counted(
        lambda: column()[
            text_input(value=query, on_change=change, key="q"),
            box(key="k", width=10, height=10, focusable=True, on_key=key),
            text(lambda: query(), key="echo"),
            text(f"{len(log)} cambios", key="log"),
        ]
    )
    pilot = App(view).pilot()
    pilot.click("q")
    pilot.type("x")
    assert value(pilot, "log") == "1 cambios"
    calls = view.calls
    pilot.focus("k")
    pilot.press("a")
    assert view.calls > calls and value(pilot, "log") == "2 cambios"


def test_a_click_in_one_window_rebuilds_the_others_whole():
    """El manejador pudo cambiar estado que lee otra ventana."""
    items = ["a"]
    n = Signal(0)

    def add():
        items.append("b")
        n.set(n() + 1)

    app = App(lambda: column()[box(key="add", width=10, height=10, on_click=add)])
    other = app.window(lambda: column()[text(lambda: f"{n()}", key="n"), text(f"{len(items)}", key="len")])
    main, second = app.pilot(), other.pilot()
    main.click("add")
    second.frame()
    assert value(second, "n") == "1" and value(second, "len") == "2"


def test_signals_set_outside_an_event_stay_partial():
    """Lo que llega solo por `Signal` (un hilo, `app.spawn`, el propio test) sigue siendo parcial."""
    import threading

    n = Signal(0)
    view = Counted(lambda: column()[text(lambda: f"{n()}", key="t")])
    pilot = App(view).pilot()
    worker = threading.Thread(target=lambda: n.set(5))
    worker.start()
    worker.join()
    pilot.frame()
    assert value(pilot, "t") == "5" and view.calls == 1


def test_a_click_rebuilds_whole_once_and_later_signals_are_partial_again():
    n = Signal(0)
    view = Counted(
        lambda: column()[
            text(lambda: f"{n()}", key="t"),
            box(key="inc", width=10, height=10, on_click=lambda: n.set(n() + 1)),
        ]
    )
    pilot = App(view).pilot()
    pilot.click("inc")
    assert value(pilot, "t") == "1" and view.calls == 2
    n.set(7)
    pilot.frame()
    assert value(pilot, "t") == "7" and view.calls == 2
