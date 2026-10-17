"""Menús nativos: la descripción que produce `aurora.menus` y su viaje al núcleo."""

import pytest

from aurora import App, Signal, _core, box, menus


def test_item_shape():
    def abrir() -> None: ...

    assert menus.item("Abrir", abrir) == {
        "type": "item",
        "label": "Abrir",
        "enabled": True,
        "action": abrir,
        "shortcut": None,
    }
    assert menus.item("Guardar", abrir, shortcut="mod+s", enabled=False)["shortcut"] == "mod+s"
    assert menus.item("Guardar", abrir, enabled=False)["enabled"] is False


def test_separator_and_submenu():
    assert menus.separator() == {"type": "separator"}
    sub = menus.submenu("Editar", menus.separator(), menus.submenu("Más"))
    assert sub == {
        "type": "submenu",
        "label": "Editar",
        "items": [{"type": "separator"}, {"type": "submenu", "label": "Más", "items": []}],
    }


def test_predefined_entries():
    assert menus.predefined("copy") == {"type": "predefined", "name": "copy"}
    with pytest.raises(ValueError, match="desconocida"):
        menus.predefined("pegar")


def test_bar_is_a_list():
    entrada = menus.item("Salir", lambda: None)
    assert menus.bar(entrada, menus.separator()) == [entrada, menus.separator()]
    assert menus.bar() == []


def test_the_app_passes_its_menu_to_the_core(monkeypatch):
    calls = []
    monkeypatch.setattr(_core, "run", lambda *args: calls.append(args))
    n = Signal(0)
    entrada = menus.item("Sumar", lambda: n.update(lambda v: v + 1), shortcut="ctrl+o")
    barra = menus.bar(menus.submenu("Archivo", entrada))
    app = App(lambda: None, menu=barra, inspector=False)  # ty: ignore[invalid-argument-type]
    app.run()
    (call,) = calls
    assert call[4] == barra
    # Sin barra, el núcleo recibe `None`.
    App(lambda: None, inspector=False).run()  # ty: ignore[invalid-argument-type]
    assert calls[1][4] is None


def test_context_menu_accepts_a_list_or_a_callable():
    entrada = menus.item("Abrir", lambda: None)
    elemento = box(on_context_menu=[entrada])
    handler = elemento.handlers["context_menu"]
    assert callable(handler)  # el núcleo pide la descripción al abrir el menú
    assert handler() == [entrada]

    dinamico = box(on_context_menu=lambda: [entrada])
    assert dinamico.handlers["context_menu"]() == [entrada]
