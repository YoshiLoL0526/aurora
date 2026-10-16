"""Elección del backend de render. Los valores se validan antes de abrir la ventana."""

import pytest

from aurora import App, text


def view():
    return text("hola")


def test_unknown_backend_is_rejected_before_opening_a_window():
    with pytest.raises(ValueError, match="'auto', 'gpu' o 'cpu'"):
        App(view).run(backend="opengl")  # ty: ignore[invalid-argument-type]


def test_unknown_backend_in_environment_is_rejected(monkeypatch):
    monkeypatch.setenv("AURORA_BACKEND", "d3d")
    with pytest.raises(ValueError, match="AURORA_BACKEND"):
        App(view).run()
