"""Identidad de la app en Windows (AUMID): derivación, registro y avisos."""

import sys
from pathlib import Path

import pytest

from aurora import App, _core


def _app(**kwargs):
    return App(lambda: None, inspector=False, **kwargs)  # ty: ignore[invalid-argument-type]


def test_a_packaged_app_derives_its_id_from_the_title(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert _app(title="Mi App Útil").app_id == "aurora.mi-app-util"
    assert _app(title="Notas", app_id="Mi.Propia").app_id == "Mi.Propia"


def test_a_script_has_no_identity_by_default(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert _app(title="Notas").app_id is None
    assert _app(title="Notas", app_id="Mi.Propia").app_id == "Mi.Propia"


def test_run_sets_and_registers_the_identity_when_packaged(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(_core, "run", lambda *args: None)
    monkeypatch.setattr(_core, "app_id_set", lambda app_id: calls.append(("set", app_id)))
    monkeypatch.setattr(_core, "app_id_register", lambda *args: calls.append(("register", args)) or True)
    _app(title="Notas").run()
    assert calls[0] == ("set", "aurora.notas")
    kind, (app_id, name, target, arguments) = calls[1]
    assert kind == "register"
    assert (app_id, name, target, arguments) == (
        "aurora.notas",
        Path(sys.executable).stem,
        sys.executable,
        None,
    )


def test_run_only_sets_the_identity_when_not_packaged(monkeypatch):
    calls = []
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(_core, "run", lambda *args: None)
    monkeypatch.setattr(_core, "app_id_set", lambda app_id: calls.append(app_id))
    monkeypatch.setattr(_core, "app_id_register", lambda *args: calls.append(args) or True)
    _app(title="Notas", app_id="Mi.Propia").run()
    assert calls == ["Mi.Propia"]  # sin registro: lo hace un instalador o `register_app_id`


def test_register_app_id_needs_an_identity(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    with pytest.raises(ValueError, match="app_id"):
        _app().register_app_id()


def test_register_app_id_points_to_the_script_in_development(monkeypatch):
    calls = []
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(_core, "app_id_register", lambda *args: calls.append(args) or True)
    monkeypatch.setattr("aurora._script_path", lambda: "/tmp/tray.py")
    assert _app(app_id="Aurora.Tray").register_app_id() is True
    assert calls == [("Aurora.Tray", "tray", sys.executable, "/tmp/tray.py")]
