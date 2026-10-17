"""Diálogos nativos: la capa Python (el núcleo va doblado; no hay pantalla)."""

from aurora import _core, dialogs


def _stub(monkeypatch, name, result):
    """Sustituye `_core.<name>` y devuelve la lista de llamadas que reciba."""
    calls = []

    def double(*args):
        calls.append(args)
        return result

    monkeypatch.setattr(_core, name, double)
    return calls


def test_open_file_passes_and_normalizes_everything(monkeypatch):
    calls = _stub(monkeypatch, "open_file", "/tmp/informe.md")
    path = dialogs.open_file(title="Abrir", directory="/tmp", filters=[("Texto", ("txt", "md"))])
    assert path == "/tmp/informe.md"
    assert calls == [("Abrir", "/tmp", [("Texto", ["txt", "md"])])]


def test_defaults_are_none(monkeypatch):
    calls = _stub(monkeypatch, "open_file", None)
    assert dialogs.open_file() is None
    assert calls == [(None, None, None)]


def test_open_files_returns_a_list(monkeypatch):
    calls = _stub(monkeypatch, "open_files", ["/a.txt", "/b.txt"])
    assert dialogs.open_files() == ["/a.txt", "/b.txt"]
    assert calls == [(None, None, None)]


def test_save_file_passes_the_default_name(monkeypatch):
    calls = _stub(monkeypatch, "save_file", "/tmp/datos.csv")
    assert dialogs.save_file(default_name="datos.csv") == "/tmp/datos.csv"
    assert calls == [(None, None, "datos.csv", None)]


def test_pick_folder(monkeypatch):
    calls = _stub(monkeypatch, "pick_folder", "/tmp")
    assert dialogs.pick_folder(title="Elige carpeta") == "/tmp"
    assert calls == [("Elige carpeta", None)]
