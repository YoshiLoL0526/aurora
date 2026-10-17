"""Notificaciones del sistema: la capa Python (el núcleo va doblado)."""

from aurora import App, _core


def _app():
    return App(lambda: None, inspector=False)  # ty: ignore[invalid-argument-type]


def test_notify_passes_title_body_and_icon(monkeypatch):
    calls = []
    monkeypatch.setattr(_core, "notify", lambda *args: calls.append(args))
    _app().notify("Listo", "El informe está generado", icon="icono.png")
    assert calls == [("Listo", "El informe está generado", "icono.png")]


def test_body_and_icon_are_optional(monkeypatch):
    calls = []
    monkeypatch.setattr(_core, "notify", lambda *args: calls.append(args))
    _app().notify("Solo título")
    assert calls == [("Solo título", "", None)]
