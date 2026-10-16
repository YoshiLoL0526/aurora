"""Hot reload: recargar el código de la app sin perder el estado de los `Signal`."""

import os
import sys
import textwrap
import time
import types
from pathlib import Path

import pytest

from aurora import App, Signal
from aurora.cli import main
from aurora.reload import enabled, keep_signals

APP = """
from aurora import App, Signal, button, column, text

clicks = Signal(0)

def view():
    return column(key="root")[
        button("Sumar", lambda: clicks.update(lambda n: n + 1), key="add"),
        text(lambda: f"{clicks()} clics", key="{label}"),
    ]

app = App(view, size=(400, 300))

if __name__ == "__main__":
    app.run()
"""


def write(path: Path, source: str) -> None:
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    # Algunos sistemas de archivos solo guardan segundos: que el cambio se note siempre.
    stamp = path.stat().st_mtime_ns + 1_000_000_000
    os.utime(path, ns=(stamp, stamp))


@pytest.fixture
def load(tmp_path, monkeypatch):
    """Ejecuta un script como lo haría `python script` (sin abrir ventana) y limpia sus módulos."""
    monkeypatch.syspath_prepend(str(tmp_path))
    before = set(sys.modules)

    def run(source: str, name: str = "app.py") -> types.ModuleType:
        path = tmp_path / name
        write(path, source)
        module = types.ModuleType("aurora_test_main")
        module.__file__ = str(path)
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
        return module

    yield run
    for name in set(sys.modules) - before:
        del sys.modules[name]


def reload(main: types.ModuleType, source: str) -> None:
    write(Path(main.__file__ or ""), source)


def test_environment_variable_enables_it(monkeypatch):
    monkeypatch.setenv("AURORA_RELOAD", "1")
    assert enabled(None) is True
    assert enabled(False) is False
    monkeypatch.delenv("AURORA_RELOAD")
    assert enabled(None) is False
    assert App(lambda: None, reload=True).reload is True  # ty: ignore[invalid-argument-type]


def test_reload_applies_new_view_and_keeps_signal_state(load):
    main = load(APP.replace("{label}", "old"))
    app = main.app
    reloader = app.watch(main)
    pilot = app.pilot()
    pilot.click("add")
    pilot.click("add")
    clicks = main.clicks
    assert clicks() == 2 and pilot.rect("old") is not None

    reload(main, APP.replace("{label}", "new"))
    assert reloader.check()
    pilot.frame()
    assert pilot.rect("new") is not None and pilot.rect("old") is None
    # Mismo Signal (no una copia): quien lo tuviera guardado sigue viendo los cambios.
    assert main.clicks is clicks and clicks() == 2
    pilot.click("add")
    assert clicks() == 3


def test_nothing_changes_without_saving(load):
    main = load(APP.replace("{label}", "old"))
    reloader = main.app.watch(main)
    assert not reloader.check()
    clicks = main.clicks
    main.app.pilot().frame()
    assert main.clicks is clicks


def test_error_is_shown_and_state_survives_until_fixed(load, capsys):
    main = load(APP.replace("{label}", "old"))
    app = main.app
    reloader = app.watch(main)
    pilot = app.pilot()
    pilot.click("add")

    reload(main, APP.replace("{label}", "old") + "\ndef roto(:\n")
    reloader.check()
    pilot.frame()
    assert pilot.rect("aurora:reload-error") is not None
    assert "SyntaxError" in capsys.readouterr().err
    # Un error de sintaxis no llega a ejecutar nada.
    assert main.clicks() == 1

    # Un error al ejecutar el módulo deja sus globales como estaban.
    reload(main, APP.replace("{label}", "old").replace("clicks = Signal(0)", "clicks = Signal(0)\n1 / 0"))
    reloader.check()
    pilot.frame()
    assert "ZeroDivisionError" in capsys.readouterr().err
    assert main.clicks() == 1 and callable(main.view)

    reload(main, APP.replace("{label}", "fixed"))
    reloader.check()
    pilot.frame()
    assert pilot.rect("aurora:reload-error") is None
    assert pilot.rect("fixed") is not None and main.clicks() == 1


def test_view_errors_are_shown_instead_of_crashing(load, capsys):
    main = load(APP.replace("{label}", "old"))
    app = main.app
    reloader = app.watch(main)
    pilot = app.pilot()

    reload(main, APP.replace("{label}", "old").replace("def view():", "def view():\n    1 / 0"))
    reloader.check()
    pilot.frame()
    assert pilot.rect("aurora:reload-error") is not None
    assert "ZeroDivisionError" in capsys.readouterr().err


def test_local_module_reload_keeps_signals_and_refreshes_importers(load, tmp_path):
    write(
        tmp_path / "estado.py",
        """
        from dataclasses import dataclass, field
        from aurora import Signal

        @dataclass
        class Estado:
            nombre: Signal = field(default_factory=lambda: Signal("Ada"))
            filtros: dict = field(default_factory=lambda: {"texto": Signal("")})

        estado = Estado()

        def saludo():
            return "Hola"
        """,
    )
    main = load(
        """
        from aurora import App, column, text
        from estado import estado, saludo

        def view():
            return column()[text(lambda: f"{saludo()}, {estado.nombre()}", key=saludo())]

        app = App(view)
        """
    )
    reloader = main.app.watch(main)
    pilot = main.app.pilot()
    estado = sys.modules["estado"]
    nombre, texto = estado.estado.nombre, estado.estado.filtros["texto"]
    nombre.set("Grace")
    texto.set("abc")

    source = (tmp_path / "estado.py").read_text(encoding="utf-8").replace('"Hola"', '"Adiós"')
    write(tmp_path / "estado.py", source)
    assert reloader.check()
    pilot.frame()
    # El script principal usa `saludo` de `estado`: se volvió a ejecutar y ve la función nueva.
    assert pilot.rect("Adiós") is not None
    assert main.estado is estado.estado
    assert estado.estado.nombre is nombre and nombre() == "Grace"
    assert estado.estado.filtros["texto"] is texto and texto() == "abc"


def test_keep_signals_rules():
    old_count, old_items = Signal(5), Signal([1, 2])
    old = {"__name__": "m", "count": old_count, "items": old_items, "pair": (Signal("a"),), "gone": Signal(1)}
    new_count, new_items, new_pair = Signal(0), Signal("texto"), Signal("b")
    new = {"__name__": "m", "count": new_count, "items": new_items, "pair": (new_pair,), "fresh": Signal(2)}
    unsubscribe_marker: list[int] = []
    new_count.subscribe(unsubscribe_marker.append)

    assert keep_signals(old, new) == 2
    # Mismo sitio y tipo compatible: se queda el antiguo, con las suscripciones del código nuevo.
    assert new["count"] is old_count and old_count() == 5
    old_count.set(6)
    assert unsubscribe_marker == [6]
    # Cambió el tipo del valor inicial: gana el nuevo.
    assert new["items"] is new_items and new_items() == "texto"
    # En una tupla no se puede sustituir: se copia el valor.
    assert new["pair"][0] is new_pair and new_pair() == "a"


def test_watcher_thread_notices_changes(load):
    main = load(APP.replace("{label}", "old"))
    reloader = main.app.watch(main)
    reloader.start()
    try:
        reload(main, APP.replace("{label}", "new"))
        deadline = time.monotonic() + 5
        while not reloader.pending and time.monotonic() < deadline:
            time.sleep(0.05)
        assert reloader.pending
    finally:
        reloader.stop()


def test_dev_command_runs_script_with_reload(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("AURORA_RELOAD", raising=False)
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    monkeypatch.setattr(sys, "path", list(sys.path))
    script = tmp_path / "demo.py"
    write(
        script,
        """
        import os, sys
        print(os.environ["AURORA_RELOAD"], os.environ.get("AURORA_INSPECTOR"), sys.argv[1:], __name__)
        """,
    )
    monkeypatch.delenv("AURORA_INSPECTOR", raising=False)
    assert main(["dev", "--inspector", str(script), "x"]) == 0
    assert capsys.readouterr().out.strip() == "1 1 ['x'] __main__"
    assert main(["dev", str(tmp_path / "missing.py")]) == 1
