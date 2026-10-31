"""Ventanas: `App.window`, su ciclo de vida y lo que se pide al núcleo nativo.

Las ventanas de verdad las crea el bucle (winit), que aquí no se ejecuta:
estos tests comprueban la API de Python con `aurora._core` sustituido por
dobles. Lo que se pinta se prueba con `Window.pilot()`, que es el mismo
`Runtime` de la ventana sin abrir ninguna.
"""

import pytest

from aurora import App, Signal, _core, _windowstate, box, column, current_window, text


class Loop:
    """Doble de `aurora._core`: apunta lo que le pediría la app."""

    def __init__(self, monkeypatch):
        self.calls = []
        for name in ("run", "window_open", "window_close", "window_set", "quit"):
            monkeypatch.setattr(_core, name, self._spy(name))

    def _spy(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record

    def of(self, name):
        return [call for call in self.calls if call[0] == name]


def view(label, key="t"):
    return lambda: column()[text(label, key=key)]


def test_the_app_opens_its_window_and_the_extra_ones(monkeypatch):
    loop = Loop(monkeypatch)
    app = App(view("principal"), title="Principal", size=(400, 300), inspector=False)
    app.window(view("detalle"), title="Detalle", size=(200, 150))
    app.run(backend="cpu")

    (call,) = loop.of("run")
    windows, backend, inspector, keep_alive, menu = call[1]
    assert [w["title"] for w in windows] == ["Principal", "Detalle"]
    assert [w["size"] for w in windows] == [(400, 300), (200, 150)]
    assert [w["id"] for w in windows] == [0, 1]  # la principal es la 0
    assert (backend, inspector, keep_alive, menu) == ("cpu", False, False, None)
    assert call[2] == {}
    assert app.running is False


def test_extra_windows_default_to_the_app_size(monkeypatch):
    loop = Loop(monkeypatch)
    app = App(view("principal"), size=(400, 300))
    app.window(view("detalle"))
    app.run()
    (call,) = loop.of("run")
    assert call[1][0][1]["size"] == (400, 300)


def test_keep_alive_is_passed_through(monkeypatch):
    loop = Loop(monkeypatch)
    App(view("x")).run(keep_alive=True)
    (call,) = loop.of("run")
    assert call[1][3] is True


def test_a_window_created_while_running_opens_at_once(monkeypatch):
    loop = Loop(monkeypatch)
    app = App(view("principal"))
    app.running = True  # como dentro de `run()`
    window = app.window(view("detalle"), title="Detalle")
    (call,) = loop.of("window_open")
    (config,) = call[1]
    assert config["id"] == window._id
    assert config["build"] == window._build
    assert (config["title"], config["size"], config["resizable"]) == ("Detalle", (960, 640), True)
    assert (config["on_close"], config["on_closed"]) == (None, app._notify_closed)


def test_close_and_open_a_window(monkeypatch):
    loop = Loop(monkeypatch)
    app = App(view("principal"))
    window = app.window(view("detalle"))
    window.close()
    app.run()
    (call,) = loop.of("run")
    assert [w["id"] for w in call[1][0]] == [0]  # la cerrada no se abre

    app.running = True
    window.open()
    (opened,) = loop.of("window_open")
    assert opened[1][0]["id"] == window._id

    window.close()
    (closed,) = loop.of("window_close")
    assert closed[1] == (window._id,)
    assert window.is_open is False
    assert repr(window) == f"<Window {window._id} 'Aurora' cerrada>"


def test_the_core_notifies_closed_windows(monkeypatch):
    Loop(monkeypatch)
    app = App(view("principal"))
    window = app.window(view("detalle"))
    app.running = True
    window.open()
    app._notify_closed(window._id)  # el usuario pulsó la X del sistema
    assert window.is_open is False
    assert window._created is False


def test_title_and_size_change_in_flight(monkeypatch):
    loop = Loop(monkeypatch)
    app = App(view("principal"))
    window = app.window(view("detalle"))
    window.title = "Otro"
    window.size = (300, 200)
    assert loop.of("window_set") == []  # aún no hay ventana en el núcleo

    app.running = True
    window.open()
    window.title = "Nuevo"
    window.size = (500, 400)
    calls = loop.of("window_set")
    assert [c[2] for c in calls] == [{"title": "Nuevo"}, {"size": (500.0, 400.0)}]


def test_on_close_travels_with_the_window(monkeypatch):
    loop = Loop(monkeypatch)

    def confirm():
        return True

    app = App(view("principal"))
    app.window(view("detalle"), on_close=confirm)
    app.run()
    (call,) = loop.of("run")
    assert call[1][0][1]["on_close"] is confirm


def test_quit_reaches_the_core(monkeypatch):
    loop = Loop(monkeypatch)
    app = App(view("principal"))
    app.quit()
    assert len(loop.of("quit")) == 1


def test_running_twice_is_an_error(monkeypatch):
    Loop(monkeypatch)
    app = App(view("principal"))
    app.running = True
    with pytest.raises(RuntimeError, match="marcha"):
        app.run()


def test_a_windows_pilot_renders_its_own_view():
    seen = Signal(0)
    app = App(view("principal"), size=(200, 100))
    window = app.window(
        lambda: column(padding=8)[box(key="c", width=10 + seen() * 10, height=10)], size=(120, 60)
    )
    pilot = window.pilot()
    assert pilot.rect("c") == (8, 8, 10, 10)
    seen.set(2)
    pilot.frame()
    assert pilot.rect("c") == (8, 8, 30, 10)


def test_both_windows_see_a_shared_signal():
    n = Signal(1)
    app = App(lambda: column()[box(key="t", width=n() * 10, height=5)], size=(200, 60))
    window = app.window(lambda: column()[box(key="t", width=n() * 20, height=5)], size=(200, 60))
    a, b = app.pilot(), window.pilot()
    assert a.rect("t")[2] == 10
    assert b.rect("t")[2] == 20
    n.set(2)
    a.frame()
    b.frame()
    assert a.rect("t")[2] == 20
    assert b.rect("t")[2] == 40


def test_main_window_handle_changes_title_and_size(monkeypatch):
    loop = Loop(monkeypatch)
    app = App(view("principal"), title="Principal", size=(400, 300), inspector=False)
    app.main.title = "Retocada"
    app.main.size = (500, 350)
    app.run()
    (call,) = loop.of("run")
    (main, *_rest) = call[1][0]
    assert main["id"] == 0
    assert (main["title"], main["size"]) == ("Retocada", (500.0, 350.0))


def test_main_window_can_be_closed_and_reopened(monkeypatch):
    loop = Loop(monkeypatch)
    app = App(view("principal"), inspector=False)
    app.main.close()
    with pytest.raises(RuntimeError, match="cerradas"):
        app.run()

    app.run(keep_alive=True)  # sin ventanas, pero viva (bandeja)
    (call,) = loop.of("run")
    assert call[1][0] == []

    app.running = True
    app.main.open()
    (opened,) = loop.of("window_open")
    assert opened[1][0]["id"] == 0
    app._notify_closed(0)  # el usuario cerró la principal
    assert app.main.is_open is False


def test_main_window_has_its_own_pilot():
    view = lambda: column(align="start")[box(key="c", width=10, height=10)]
    app = App(view, size=(100, 60), inspector=False)
    assert app.main.pilot().rect("c") == (0.0, 0.0, 10.0, 10.0)


def test_a_windows_view_renders_to_png(tmp_path):
    app = App(view("principal"), size=(120, 60))
    window = app.window(view("detalle"), size=(120, 60))
    window.render_png(str(tmp_path / "detalle.png"))
    assert (tmp_path / "detalle.png").stat().st_size > 0


# Opciones de ventana: tamaños límite, posición, maximizada, pantalla completa, recordar.


def test_window_options_travel_to_the_core(monkeypatch):
    loop = Loop(monkeypatch)
    app = App(
        view("principal"),
        size=(800, 600),
        resizable=False,
        min_size=(400, 300),
        max_size=(1600, 1200),
        position=(40, 60),
        maximized=True,
        always_on_top=True,
    )
    app.window(view("detalle"), fullscreen=True, position=(-100, 0))
    app.run()
    (call,) = loop.of("run")
    main, extra = call[1][0]
    assert main["resizable"] is False
    assert (main["min_size"], main["max_size"]) == ((400.0, 300.0), (1600.0, 1200.0))
    assert (main["position"], main["check_position"]) == ((40.0, 60.0), False)
    assert (main["maximized"], main["fullscreen"], main["always_on_top"]) == (True, False, True)
    assert (extra["position"], extra["fullscreen"], extra["maximized"]) == ((-100.0, 0.0), True, False)
    assert (extra["min_size"], extra["max_size"], extra["resizable"]) == (None, None, True)


@pytest.mark.parametrize(
    ("kwargs", "error", "match"),
    [
        ({"size": (-10, 300)}, ValueError, "`size` debe tener ancho y alto positivos"),
        ({"size": (0, 300)}, ValueError, "`size` debe tener ancho y alto positivos"),
        ({"min_size": (500, 0)}, ValueError, "`min_size` debe tener ancho y alto positivos"),
        ({"min_size": (500, 400), "max_size": (300, 600)}, ValueError, "no puede ser mayor"),
        ({"position": (float("nan"), 0)}, ValueError, "`position` debe ser finito"),
        ({"position": 10}, TypeError, "`position` debe ser un par"),
        ({"max_size": ("a", 1)}, TypeError, "`max_size` debe ser un par"),
        ({"remember": "../fuera"}, ValueError, "`remember` debe ser un nombre de carpeta"),
        ({"remember": ""}, ValueError, "`remember`"),
    ],
)
def test_invalid_window_options_are_clear_errors(kwargs, error, match):
    with pytest.raises(error, match=match):
        App(view("x"), **kwargs)


def test_invalid_options_of_an_extra_window(monkeypatch):
    Loop(monkeypatch)
    app = App(view("x"))
    with pytest.raises(ValueError, match="no puede ser mayor"):
        app.window(view("y"), min_size=(500, 500), max_size=(400, 400))
    with pytest.raises(ValueError, match=r"necesita `App\(remember=...\)`"):
        app.window(view("y"), remember="ajustes")
    with pytest.raises(ValueError, match="reservado"):
        App(view("x"), remember="mi-app").window(view("y"), remember="main")


def test_the_core_also_rejects_invalid_sizes():
    with pytest.raises(ValueError, match="`size` debe ser positivo"):
        _core.window_set(12345, size=(-1, 10))
    with pytest.raises(ValueError, match="`position` debe ser finita"):
        _core.window_set(12345, position=(float("inf"), 0))


def test_options_change_in_flight(monkeypatch):
    loop = Loop(monkeypatch)
    app = App(view("principal"))
    window = app.window(view("detalle"), max_size=(900, 700))
    window.position = (10, 20)
    window.maximized = True
    assert loop.of("window_set") == []  # aún no existe: viaja con la configuración
    assert (window.position, window.maximized) == ((10.0, 20.0), True)

    app.running = True
    window.open()
    (opened,) = loop.of("window_open")
    assert (opened[1][0]["position"], opened[1][0]["maximized"]) == ((10.0, 20.0), True)
    window.position = (30, 40)
    window.maximized = False
    window.fullscreen = True
    window.always_on_top = True
    window.resizable = False
    window.min_size = (200, 100)
    window.max_size = None
    window.min_size = None
    window.max_size = (100, 100)
    with pytest.raises(ValueError, match="no puede ser mayor"):
        window.min_size = (300, 300)
    assert window.min_size is None
    calls = [c[2] for c in loop.of("window_set")]
    assert calls == [
        {"position": (30.0, 40.0)},
        {"maximized": False},
        {"fullscreen": True},
        {"always_on_top": True},
        {"resizable": False},
        {"min_size": (200.0, 100.0)},
        {"max_size": (0.0, 0.0)},  # (0, 0): sin límite
        {"min_size": (0.0, 0.0)},
        {"max_size": (100.0, 100.0)},
    ]


def test_reading_an_open_window_asks_the_core(monkeypatch):
    Loop(monkeypatch)
    state = {
        "size": (1200.0, 800.0),
        "position": (5.0, 6.0),
        "maximized": True,
        "fullscreen": False,
        "restored_size": (700.0, 500.0),
        "restored_position": (100.0, 80.0),
    }
    monkeypatch.setattr(_core, "window_state", lambda id: state)
    app = App(view("principal"), size=(640, 480))
    assert app.main.size == (640.0, 480.0)  # sin abrir: lo pedido
    app.running = True
    app.main._created = True
    assert (app.main.size, app.main.position, app.main.maximized) == ((1200.0, 800.0), (5.0, 6.0), True)

    # Al cerrarse se queda con lo restaurable, para reabrirla igual.
    app._notify_closed(0)
    assert app.main.is_open is False
    assert (app.main._size, app.main._position, app.main._maximized) == ((700.0, 500.0), (100.0, 80.0), True)


def _state(size, position, maximized=False, restored=None):
    restored_size, restored_position = restored or (size, position)
    return {
        "size": size,
        "position": position,
        "maximized": maximized,
        "fullscreen": False,
        "restored_size": restored_size,
        "restored_position": restored_position,
    }


def test_remember_saves_on_close_and_restores_next_time(monkeypatch, tmp_path):
    Loop(monkeypatch)
    monkeypatch.setattr(_windowstate, "config_dir", lambda: tmp_path)
    states = {
        0: _state((1920.0, 1000.0), (-8.0, -8.0), True, ((700.0, 500.0), (120.0, 90.0))),
        1: _state((300.0, 200.0), (900.0, 50.0)),
        2: _state((640.0, 480.0), (0.0, 0.0)),
    }
    monkeypatch.setattr(_core, "window_state", states.get)

    app = App(view("principal"), remember="mi-app", size=(640, 480))
    app.window(view("ajustes"), remember="ajustes")
    app.window(view("sin recordar"))
    app.run()
    for window_id in (0, 1, 2):  # el bucle termina y avisa del cierre de cada una
        app._notify_closed(window_id)

    assert (tmp_path / "mi-app" / "window-state.json").exists()
    assert _windowstate.load("mi-app") == {
        "main": {"size": [700.0, 500.0], "position": [120.0, 90.0], "maximized": True},
        "ajustes": {"size": [300.0, 200.0], "position": [900.0, 50.0], "maximized": False},
    }

    loop = Loop(monkeypatch)
    again = App(view("principal"), remember="mi-app", size=(640, 480))
    again.window(view("ajustes"), remember="ajustes", size=(100, 100))
    again.run()
    (call,) = loop.of("run")
    main, extra = call[1][0]
    assert (main["size"], main["position"], main["maximized"]) == ((700.0, 500.0), (120.0, 90.0), True)
    assert main["check_position"] is True  # el núcleo comprueba que caiga en algún monitor
    assert (extra["size"], extra["position"], extra["maximized"]) == ((300.0, 200.0), (900.0, 50.0), False)


def test_a_broken_remember_file_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setattr(_windowstate, "config_dir", lambda: tmp_path)
    folder = tmp_path / "rota"
    folder.mkdir()
    (folder / "window-state.json").write_text("{no es json", encoding="utf-8")
    assert App(view("x"), remember="rota", size=(640, 480)).main._config()["size"] == (640.0, 480.0)

    (folder / "window-state.json").write_text(
        '{"main": {"size": [-5, "x"], "position": [1, 2, 3], "maximized": "sí"}}', encoding="utf-8"
    )
    config = App(view("x"), remember="rota", size=(640, 480)).main._config()
    assert (config["size"], config["position"], config["maximized"]) == ((640.0, 480.0), None, False)


def test_size_is_kept_within_the_limits(monkeypatch):
    loop = Loop(monkeypatch)
    app = App(view("principal"), size=(1200, 200), min_size=(300, 250), max_size=(900, 700))
    app.run()
    (call,) = loop.of("run")
    assert call[1][0][0]["size"] == (900.0, 250.0)  # no todos los sistemas lo recortan solos

    app.running = True
    app.main._created = True
    app.main.size = (2000, 2000)
    app.main.max_size = None
    app.main.min_size = (1000, 800)
    assert app.main._size == (1000.0, 800.0)
    calls = [c[2] for c in loop.of("window_set")]
    assert calls == [{"size": (900.0, 700.0)}, {"max_size": (0.0, 0.0)}, {"min_size": (1000.0, 800.0)}]


def test_frameless_windows_and_their_buttons(monkeypatch):
    loop = Loop(monkeypatch)
    app = App(view("principal"), decorations=False)
    window = app.window(view("detalle"), decorations=False)
    assert (app.main.decorations, window.decorations) == (False, False)
    app.running = True
    window.open()
    (opened,) = loop.of("window_open")
    assert opened[1][0]["decorations"] is False
    window.decorations = True
    window.minimize()
    window.request_close()  # como el botón del sistema: el bucle pasa por `on_close`
    assert [c[2] for c in loop.of("window_set")] == [{"decorations": True}, {"minimized": True}]
    assert loop.of("window_close") == [("window_close", (window._id,), {"ask": True})]


def test_the_main_window_travels_frameless(monkeypatch):
    loop = Loop(monkeypatch)
    App(view("principal"), decorations=False).run()
    (run,) = loop.of("run")
    assert run[1][0][0]["decorations"] is False


def test_current_window_is_the_one_being_built():
    seen = []
    app = App(lambda: seen.append(current_window()) or column())
    extra = app.window(lambda: seen.append(current_window()) or column())
    app.pilot()
    extra.pilot()
    assert seen == [app.main, extra]
