"""Accesibilidad: la semántica que declara la vista (`role`, `label`, estados) y el
árbol que ven los lectores de pantalla (`Pilot.a11y_tree`)."""

import pytest

from aurora import App, Signal, box, button, column, image, row, scroll, text, text_input
from aurora._icons import _CHECK
from aurora.components import (
    checkbox,
    dialog,
    progress,
    radio,
    select,
    slider,
    switch,
    tabs,
    virtual_list,
)


def _pilot(view, size=(320, 240), scale=1.0):
    return App(view, size=size).pilot(scale=scale)


def _node(pilot, key):
    for node in pilot.a11y_tree():
        if node["key"] == key:
            return node
    raise AssertionError(f"no hay nodo con key {key!r} en el árbol de accesibilidad")


def _role_of(pilot, role):
    return [n for n in pilot.a11y_tree() if n["role"] == role]


def test_rol_desconocido_es_error_claro():
    with pytest.raises(ValueError, match="rol de accesibilidad desconocido"):
        _pilot(lambda: box(role="buton"))


def test_live_desconocido_es_error_claro():
    with pytest.raises(ValueError, match="live desconocido"):
        _pilot(lambda: box(live="shouty"))


def test_un_label_con_dolar_no_se_resuelve_como_token():
    # `label` es texto literal: un "$5.00" no es un token del tema.
    _pilot(lambda: box(role="button", label="$5.00", key="price")).settle()


def test_los_props_de_accesibilidad_no_afectan_al_layout():
    plain = _pilot(lambda: box(key="b", width=100, height=20))
    marked = _pilot(lambda: box(key="b", width=100, height=20, role="checkbox", label="Acepto", checked=True))
    assert plain.rect("b") == marked.rect("b")


def test_el_arbol_tiene_la_ventana_como_raiz():
    tree = _pilot(lambda: box()).a11y_tree()
    root = next(n for n in tree if n["id"] == 0)
    assert root["role"] == "window"
    assert root["focused"]  # sin foco, la raíz lo tiene
    assert root["bounds"] == (0.0, 0.0, 320.0, 240.0)


def test_el_texto_es_una_etiqueta_con_su_valor():
    node = _node(_pilot(lambda: text("Hola", key="t")), "t")
    assert node["role"] == "label"
    assert node["value"] == "Hola"


def test_el_boton_lleva_su_nombre_y_no_duplica_el_texto():
    pilot = _pilot(lambda: button("Guardar", lambda: None, key="save"))
    save = _node(pilot, "save")
    assert save["role"] == "button"
    assert save["label"] == "Guardar"
    assert {"click", "focus"} <= set(save["actions"])
    # El texto visible no es un nodo aparte: el nombre lo lleva el botón.
    assert _role_of(pilot, "label") == []


def test_el_foco_aparece_en_el_arbol():
    pilot = _pilot(lambda: column()[button("A", lambda: None, key="a"), button("B", lambda: None, key="b")])
    pilot.focus("b")
    tree = pilot.a11y_tree()
    focused = [n["key"] for n in tree if n["focused"]]
    assert focused == ["b"]


def test_la_casilla_anuncia_su_estado_y_se_actualiza():
    done = Signal(False)
    pilot = _pilot(lambda: checkbox(done, "Acepto", key="terms"))
    assert _node(pilot, "terms")["checked"] is False
    pilot.click("terms")
    assert _node(pilot, "terms")["checked"] is True
    assert done() is True


def test_el_interruptor_es_un_switch():
    on = Signal(True)
    node = _node(_pilot(lambda: switch(on, "Avisos", key="sw")), "sw")
    assert node["role"] == "switch"
    assert node["label"] == "Avisos"
    assert node["checked"] is True


def test_el_grupo_de_radios_anuncia_posicion_y_seleccion():
    picked = Signal("b")
    pilot = _pilot(lambda: radio([("a", "Uno"), ("b", "Dos")], picked, key="r"))
    assert _role_of(pilot, "radiogroup")
    radios = _role_of(pilot, "radio")
    assert [(r["label"], r["checked"], r["position_in_set"], r["set_size"]) for r in radios] == [
        ("Uno", False, 1, 2),
        ("Dos", True, 2, 2),
    ]


def test_el_slider_anuncia_valor_y_rango():
    value = Signal(0.25)
    node = _node(_pilot(lambda: slider(value, key="vol")), "vol")
    assert node["role"] == "slider"
    assert node["numeric_value"] == pytest.approx(0.25)
    assert node["value_min"] == 0.0
    assert node["value_max"] == 1.0
    assert {"increment", "decrement"} <= set(node["actions"])


def test_el_campo_anuncia_valor_y_pista():
    text_ = Signal("")
    pilot = _pilot(lambda: text_input(text_, placeholder="Tu nombre", key="name"))
    name = _node(pilot, "name")
    assert name["role"] == "textbox"
    assert name["value"] == ""
    assert name["placeholder"] == "Tu nombre"
    assert "set_value" in name["actions"]
    pilot.focus("name")
    pilot.type("Ada")
    assert _node(pilot, "name")["value"] == "Ada"


def test_la_imagen_sin_alt_es_decorativa():
    pilot = _pilot(
        lambda: row()[image(_CHECK, width=12, key="icon"), image(_CHECK, width=12, alt="Visto", key="ok")]
    )
    assert _node(pilot, "ok")["label"] == "Visto"
    assert [n for n in pilot.a11y_tree() if n["key"] == "icon"] == []


def test_hidden_queda_fuera_del_arbol():
    pilot = _pilot(
        lambda: column()[box(key="box", width=10, height=10), text("secreto", key="s", hidden=True)]
    )
    assert [n for n in pilot.a11y_tree() if n["key"] == "s"] == []


def test_las_cajas_decorativas_no_aparecen():
    pilot = _pilot(lambda: box(key="empty", width=50, height=50))
    assert [n for n in pilot.a11y_tree() if n["key"] == "empty"] == []


def test_las_pestanas_anuncian_la_activa():
    tab = Signal("a")
    pilot = _pilot(lambda: tabs([("a", "Uno"), ("b", "Dos")], tab, key="tabs"))
    assert _role_of(pilot, "tablist")
    active = [n for n in _role_of(pilot, "tab") if n["selected"]]
    assert [n["label"] for n in active] == ["Uno"]


def test_el_desplegable_abre_su_lista_con_opciones():
    value = Signal("x")
    pilot = _pilot(lambda: select(value, [("x", "Opción X"), ("y", "Opción Y")], key="sel"))
    sel = _node(pilot, "sel")
    assert sel["role"] == "combobox"
    assert sel["value"] == "Opción X"
    assert sel["expanded"] is False
    assert "expand" in sel["actions"]

    pilot.click("sel")
    assert _node(pilot, "sel")["expanded"] is True
    assert _role_of(pilot, "listbox")
    options = _role_of(pilot, "option")
    assert [(o["label"], o["selected"], o["position_in_set"]) for o in options] == [
        ("Opción X", True, 1),
        ("Opción Y", False, 2),
    ]


def test_la_barra_de_progreso_se_anuncia_y_no_se_ajusta():
    node = _node(_pilot(lambda: progress(0.4, key="prog")), "prog")
    assert node["role"] == "progressbar"
    assert node["numeric_value"] == pytest.approx(0.4)
    assert node["actions"] == []


def test_el_dialogo_es_modal_y_toma_el_foco():
    opened = Signal(True)
    pilot = _pilot(lambda: dialog(opened, column()[text("¿Seguro?")], title="Confirmar", key="dlg"))
    dlg = _node(pilot, "dlg/0")
    assert dlg["role"] == "dialog"
    assert dlg["modal"] is True
    assert dlg["label"] == "Confirmar"
    assert dlg["focused"]


def test_la_lista_virtual_anuncia_posiciones():
    pilot = _pilot(
        lambda: virtual_list(100, lambda i: row()[text(str(i))], item_height=24, key="vl"),
        size=(320, 200),
    )
    assert _role_of(pilot, "list")
    items = _role_of(pilot, "listitem")
    assert items and items[0]["position_in_set"] == 1 and items[0]["set_size"] == 100


def test_los_bounds_son_logicos_con_escala():
    view = lambda: column()[box(key="b", width=100, height=20, role="region")]
    pilot = _pilot(view, scale=2.0)
    assert _node(pilot, "b")["bounds"] == (0.0, 0.0, 100.0, 20.0)


def test_los_ids_y_el_foco_sobreviven_a_una_reconstruccion():
    # Los ids son estables por key: el lector conserva el nodo (y su foco)
    # aunque la vista se reconstruya.
    count = Signal(0)
    pilot = _pilot(lambda: column()[button("A", lambda: None, key="a"), text(f"{count()}", key="t")])
    before = {n["key"]: n["id"] for n in pilot.a11y_tree()}
    pilot.a11y_action("a", "focus")
    count.set(1)
    pilot.settle()
    after = {n["key"]: n["id"] for n in pilot.a11y_tree()}
    assert after["a"] == before["a"]
    assert after["t"] == before["t"]
    assert pilot.focused == "a"


# --- Acciones del lector (Pilot.a11y_action) --------------------------------


def test_la_accion_click_activa_el_nodo():
    count = Signal(0)
    pilot = _pilot(lambda: button("Sumar", lambda: count.update(lambda n: n + 1), key="add"))
    pilot.a11y_action("add", "click")
    assert count() == 1


def test_la_accion_click_alterna_una_casilla():
    done = Signal(False)
    pilot = _pilot(lambda: checkbox(done, "Acepto", key="terms"))
    pilot.a11y_action("terms", "click")
    assert done() is True
    assert _node(pilot, "terms")["checked"] is True


def test_la_accion_focus_mueve_el_foco():
    pilot = _pilot(lambda: column()[button("A", lambda: None, key="a"), button("B", lambda: None, key="b")])
    pilot.a11y_action("b", "focus")
    assert pilot.focused == "b"
    assert [n["key"] for n in pilot.a11y_tree() if n["focused"]] == ["b"]


def test_el_foco_del_lector_sobre_texto_no_se_pierde():
    pilot = _pilot(lambda: column()[text("Un párrafo", key="p")])
    pilot.a11y_action("p", "focus")
    assert pilot.focused == "p"


def test_set_value_escribe_en_el_campo():
    value = Signal("")
    changes = []
    pilot = _pilot(lambda: text_input(value, on_change=changes.append, key="name"))
    pilot.a11y_action("name", "set_value", "Ada")
    assert value() == "Ada"
    assert _node(pilot, "name")["value"] == "Ada"
    assert changes == ["Ada"]


def test_set_value_y_pasos_ajustan_el_slider():
    value = Signal(0.5)
    pilot = _pilot(lambda: slider(value, min=0.0, max=1.0, key="vol"))
    pilot.a11y_action("vol", "set_value", 0.75)
    assert value() == pytest.approx(0.75)
    pilot.a11y_action("vol", "increment")
    assert value() == pytest.approx(0.8)
    pilot.a11y_action("vol", "decrement")
    pilot.a11y_action("vol", "decrement")
    assert value() == pytest.approx(0.7)


def test_la_accion_expand_abre_el_desplegable():
    # Key distinta a la del test de despliegue: `open_signal` guarda el estado
    # por key entre vistas del mismo proceso.
    value = Signal("x")
    pilot = _pilot(lambda: select(value, [("x", "Opción X"), ("y", "Opción Y")], key="pick"))
    pilot.a11y_action("pick", "expand")
    assert _node(pilot, "pick")["expanded"] is True
    assert _role_of(pilot, "option")


def test_la_accion_de_scroll_trae_el_nodo_a_la_vista():
    view = lambda: scroll(key="list", height=60)[
        [button(f"{i}", lambda: None, key=f"b{i}", height=40) for i in range(10)]
    ]
    pilot = _pilot(view, size=(320, 200))
    pilot.a11y_action("b7", "scroll_into_view")
    _, dy = pilot.scroll_offset("list")  # (x, y): aquí importa la vertical
    assert dy > 0


def test_accion_desconocida_y_nodo_inexistente():
    pilot = _pilot(lambda: button("A", lambda: None, key="a"))
    with pytest.raises(ValueError, match="acción desconocida"):
        pilot.a11y_action("a", "summon")
    with pytest.raises(LookupError, match="no hay ningún nodo"):
        pilot.a11y_action("nope", "click")
