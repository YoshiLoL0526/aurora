"""Bandeja del sistema: la capa Python (el núcleo va doblado)."""

from aurora import App, _core, menus


def _stub(monkeypatch, name):
    calls = []

    def double(*args):
        calls.append(args)

    monkeypatch.setattr(_core, name, double)
    return calls


def _app():
    return App(lambda: None, inspector=False)  # ty: ignore[invalid-argument-type]


def test_tray_configures_the_icon_tooltip_and_menu(monkeypatch):
    shown = _stub(monkeypatch, "tray_show")

    def abrir() -> None: ...

    def al_clic(button: str) -> None: ...

    app = _app()
    app.tray(
        "icono.png",
        tooltip="Notas",
        menu=[menus.item("Abrir", abrir), menus.separator()],
        on_click=al_clic,
    )
    (call,) = shown
    icon, tooltip, menu, on_click, on_double_click, template = call
    assert (icon, tooltip, on_double_click, template) == ("icono.png", "Notas", None, False)
    assert menu == [menus.item("Abrir", abrir), menus.separator()]
    assert on_click is al_clic


def test_a_tray_keeps_the_app_alive_without_windows(monkeypatch):
    _stub(monkeypatch, "tray_show")
    runs = _stub(monkeypatch, "run")
    app = _app()
    app.tray(b"\x89PNG")
    assert app._keep_alive is True

    app.run()
    (call,) = runs
    assert call[3] is True  # keep_alive


def test_tray_hide_gives_the_lifetime_back(monkeypatch):
    _stub(monkeypatch, "tray_show")
    hidden = _stub(monkeypatch, "tray_hide")
    runs = _stub(monkeypatch, "run")
    app = _app()
    app.tray("icono.png")
    app.tray_hide()
    assert app._keep_alive is False
    assert len(hidden) == 1

    app.run()
    (call,) = runs
    assert call[3] is False


def test_keep_alive_explicit_wins_over_the_tray(monkeypatch):
    _stub(monkeypatch, "tray_show")
    runs = _stub(monkeypatch, "run")
    app = _app()
    app.tray("icono.png")
    app.run(keep_alive=False)
    (call,) = runs
    assert call[3] is False
