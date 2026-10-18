"""Notificaciones del sistema: la capa Python (el núcleo va doblado)."""

from aurora import App, _core


def _app(**kwargs):
    return App(lambda: None, inspector=False, **kwargs)  # ty: ignore[invalid-argument-type]


def test_notify_passes_title_body_and_icon(monkeypatch):
    calls = []
    monkeypatch.setattr(_core, "notify", lambda *args: calls.append(args))
    _app().notify("Listo", "El informe está generado", icon="icono.png")
    assert calls == [("Listo", "El informe está generado", "icono.png", None, None)]


def test_body_and_icon_are_optional(monkeypatch):
    calls = []
    monkeypatch.setattr(_core, "notify", lambda *args: calls.append(args))
    _app().notify("Solo título")
    assert calls == [("Solo título", "", None, None, None)]


def test_notify_carries_the_app_identity(monkeypatch):
    calls = []
    monkeypatch.setattr(_core, "notify", lambda *args: calls.append(args))
    _app(app_id="Mi.Propia").notify("Hola", "con identidad")
    assert calls == [("Hola", "con identidad", None, "Mi.Propia", None)]


def test_on_click_travels_to_the_core(monkeypatch):
    calls = []
    monkeypatch.setattr(_core, "notify", lambda *args: calls.append(args))

    def al_clic() -> None: ...

    _app().notify("Listo", "con callback", on_click=al_clic)
    assert calls == [("Listo", "con callback", None, None, al_clic)]
