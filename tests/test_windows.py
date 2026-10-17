"""Ventanas: `App.window`, su ciclo de vida y lo que se pide al núcleo nativo.

Las ventanas de verdad las crea el bucle (winit), que aquí no se ejecuta:
estos tests comprueban la API de Python con `aurora._core` sustituido por
dobles. Lo que se pinta se prueba con `Window.pilot()`, que es el mismo
`Runtime` de la ventana sin abrir ninguna.
"""

import pytest

from aurora import App, Signal, _core, box, column, text


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
    assert call[1][1] == window._build
    assert call[1][2:] == ("Detalle", (960, 640), True, None, app._notify_closed)


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
    assert opened[1][0] == window._id

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
    assert opened[1][0] == 0
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
