"""Cada componente público, completo: render, interacción, accesibilidad y teclado.

`COVERAGE` es la matriz: por componente, la prueba que cubre cada aspecto (o el
motivo por el que no aplica). Las pruebas parametrizadas de este archivo cubren
lo común a todos (se pinta con sus valores por defecto en los dos temas,
anuncia rol y nombre, los decorativos no roban foco ni clics) y las demás
filas apuntan a pruebas más profundas en otros archivos. `docs/coverage.md` se
genera desde aquí; para regenerarlo:

    AURORA_UPDATE_COVERAGE=1 uv run pytest tests/test_coverage.py
"""

from __future__ import annotations

import ast
import inspect
import os
from collections.abc import Callable
from datetime import date, time
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from test_render import _png_rows

import aurora
from aurora import (
    DAYLIGHT,
    MIDNIGHT,
    App,
    Column,
    Signal,
    accordion,
    avatar,
    badge,
    button,
    canvas,
    card,
    chart,
    checkbox,
    color_picker,
    column,
    combobox,
    date_picker,
    dialog,
    divider,
    field,
    markdown,
    menu,
    number_input,
    pages,
    popover,
    progress,
    radio,
    rich_text,
    segmented,
    select,
    skeleton,
    slider,
    sortable,
    span,
    spinner,
    splitter,
    stat,
    switch,
    table,
    tabs,
    text,
    text_input,
    textarea,
    time_picker,
    title_bar,
    toast,
    tooltip,
    tree,
    virtual_list,
)

TESTS = Path(__file__).parent
DOC = TESTS.parent / "docs" / "coverage.md"
_MODULES = ("aurora.components.", "aurora.charts", "aurora.canvas", "aurora.table", "aurora.richtext")


def public_components() -> list[str]:
    """Las funciones públicas que construyen un componente (no las primitivas de `elements`)."""
    return sorted(
        name
        for name in aurora.__all__
        if inspect.isfunction(obj := getattr(aurora, name))
        and obj.__module__.startswith(_MODULES)
        and name != "span"  # un trozo de `rich_text`, no un componente
    )


@pytest.fixture(autouse=True)
def _fresh_component_state():
    from aurora.components import _state

    for name, store in vars(_state).items():
        if not name.startswith("__") and isinstance(store, dict):
            store.clear()


# Cada componente con sus valores por defecto (más lo imprescindible) y la key `x`
# donde la acepta. Se construyen dentro de la vista: `title_bar` necesita la ventana.
GALLERY: dict[str, Callable[[], Any]] = {
    "accordion": lambda: accordion([("u", "Uno", text("contenido"))], Signal(None), key="x"),
    "avatar": lambda: avatar("Ada Lovelace", key="x"),
    "badge": lambda: badge("nuevo"),
    "button": lambda: button("Guardar", lambda: None, key="x"),
    "canvas": lambda: canvas(lambda c: c.circle(20, 20, 12, fill="$primary"), label="Logo", key="x"),
    "card": lambda: card(key="x")[text("hola")],
    "chart": lambda: chart(np.sin(np.arange(40) / 4), label="Ventas", key="x"),
    "checkbox": lambda: checkbox(Signal(False), "Acepto", key="x"),
    "color_picker": lambda: color_picker(Signal("#7C5CFF"), key="x"),
    "combobox": lambda: combobox(Signal(None), ["uno", "dos"], label="Fruta", key="x"),
    "date_picker": lambda: date_picker(Signal(date(2026, 1, 5)), label="Fecha", key="x"),
    "dialog": lambda: dialog(Signal(True), text("cuerpo"), title="Aviso", key="x"),
    "divider": lambda: divider(key="x"),
    "field": lambda: field(text_input(Signal(""), key="campo"), label="Nombre", hint="Como en el DNI"),
    "markdown": lambda: markdown("# Título\n\nTexto con **negrita**", key="x"),
    "menu": lambda: menu(button("Más", lambda: None), [("Abrir", lambda: None)], key="x"),
    "number_input": lambda: number_input(Signal(3), label="Cantidad", key="x"),
    "pages": lambda: pages(Signal("a"), {"a": lambda: text("Portada")}, key="x"),
    "popover": lambda: popover(button("Filtros", lambda: None), text("panel"), key="x"),
    "progress": lambda: progress(0.4, label="Carga", key="x"),
    "radio": lambda: radio([("a", "Alfa"), ("b", "Beta")], Signal("a"), key="x"),
    "rich_text": lambda: rich_text("hola ", span("mundo", weight=700), key="x"),
    "segmented": lambda: segmented([("a", "Día"), ("b", "Semana")], Signal("a"), key="x"),
    "select": lambda: select(Signal("a"), [("a", "Alfa"), ("b", "Beta")], label="Letra", key="x"),
    "skeleton": lambda: skeleton(lines=2),
    "slider": lambda: slider(Signal(0.5), label="Volumen", key="x"),
    "sortable": lambda: sortable(["uno", "dos"], lambda s: card()[text(s)], key="x"),
    "spinner": lambda: spinner(key="x"),
    "splitter": lambda: splitter(text("Izquierda"), text("Derecha"), key="x", height=120),
    "stat": lambda: stat("Ventas", "1.200", "+4 %"),
    "switch": lambda: switch(Signal(True), "Wifi", key="x"),
    "table": lambda: table([{"n": 1}, {"n": 2}], [Column("n", "Número")], key="x", height=140),
    "tabs": lambda: tabs([("a", "Alfa"), ("b", "Beta")], Signal("a"), key="x"),
    "text_input": lambda: text_input(Signal(""), placeholder="Buscar", label="Buscar", key="x"),
    "textarea": lambda: textarea(Signal(""), placeholder="Notas", label="Notas", key="x"),
    "time_picker": lambda: time_picker(Signal(time(9, 30)), label="Hora", key="x"),
    "title_bar": lambda: title_bar("Notas", controls="windows"),
    "toast": lambda: toast("Guardado", on_close=lambda: None, key="x"),
    "tooltip": lambda: tooltip(button("Ayuda", lambda: None, key="x"), "Abre la guía"),
    "tree": lambda: tree([("raíz", [("hoja", [])])], lambda n: n[1], label=lambda n: n[0], key="x"),
    "virtual_list": lambda: virtual_list(3, lambda i: text(f"fila {i}"), item_height=30, key="x", height=120),
}

# Rol y nombre que un lector de pantalla tiene que encontrar (el nombre es la
# etiqueta o, en los textos, su valor).
ANNOUNCED: dict[str, tuple[str, str]] = {
    "accordion": ("button", "Uno"),
    "avatar": ("image", "Ada Lovelace"),
    "badge": ("label", "nuevo"),
    "button": ("button", "Guardar"),
    "canvas": ("canvas", "Logo"),
    "card": ("label", "hola"),
    "chart": ("figure", "Ventas"),
    "checkbox": ("checkbox", "Acepto"),
    "color_picker": ("combobox", "Color"),
    "combobox": ("combobox", "Fruta"),
    "date_picker": ("combobox", "Fecha"),
    "dialog": ("dialog", "Aviso"),
    "divider": ("separator", ""),
    "field": ("textbox", "Nombre"),
    "markdown": ("heading", "Título"),
    "menu": ("button", "Más"),
    "number_input": ("spinbutton", "Cantidad"),
    "pages": ("label", "Portada"),
    "popover": ("button", "Filtros"),
    "progress": ("progressbar", "Carga"),
    "radio": ("radio", "Alfa"),
    "rich_text": ("label", "hola mundo"),
    "segmented": ("radio", "Día"),
    "select": ("combobox", "Letra"),
    "skeleton": ("", ""),  # decorativo: no aparece en el árbol
    "slider": ("slider", "Volumen"),
    "sortable": ("listitem", "uno"),
    "spinner": ("progressbar", ""),
    "splitter": ("separator", "Redimensionar paneles"),
    "stat": ("label", "1.200"),
    "switch": ("switch", "Wifi"),
    "table": ("columnheader", "Número"),
    "tabs": ("tab", "Alfa"),
    "text_input": ("textbox", "Buscar"),
    "textarea": ("textarea", "Notas"),
    "time_picker": ("combobox", "Hora"),
    "title_bar": ("button", "Cerrar"),
    "toast": ("status", ""),
    "tooltip": ("button", "Ayuda"),
    "tree": ("treeitem", "raíz"),
    "virtual_list": ("list", ""),
}

# Sin manejadores propios: no entran en el orden de Tab ni se quedan con los clics.
STATIC = [
    "avatar",
    "badge",
    "card",
    "divider",
    "pages",
    "progress",
    "rich_text",
    "skeleton",
    "spinner",
    "stat",
]


def _app(
    name: str, *, theme: Any = MIDNIGHT, size: tuple[float, float] = (420, 320), after: Any = None
) -> App:
    return App(lambda: column(padding=12, gap=8, grow=1)[GALLERY[name](), after], size=size, theme=theme)


@pytest.mark.parametrize("theme", [DAYLIGHT, MIDNIGHT], ids=["claro", "oscuro"])
@pytest.mark.parametrize("name", sorted(GALLERY))
def test_component_renders_with_its_defaults(name: str, theme: Any, tmp_path: Path) -> None:
    out = tmp_path / f"{name}.png"
    _app(name, theme=theme).pilot().png(str(out))
    channels, rows = _png_rows(out)
    background = bytes(rows[2][:channels])  # esquina, dentro del padding: el fondo del tema
    painted = sum(
        1
        for line in rows
        for i in range(0, len(line), channels)
        if max(abs(a - b) for a, b in zip(line[i : i + 3], background, strict=False)) > 8
    )
    assert painted > 40, f"{name} no pinta nada distinto del fondo"


def _announced(pilot: Any) -> list[tuple[str, str]]:
    return [(n["role"], n.get("label") or n.get("value") or "") for n in pilot.a11y_tree()]


@pytest.mark.parametrize("name", sorted(GALLERY))
def test_component_announces_its_role_and_name(name: str) -> None:
    role, label = ANNOUNCED[name]
    nodes = _announced(_app(name).pilot())
    if not role:  # decorativo: nada más que la ventana
        assert {r for r, _ in nodes} <= {"window", "generic"}, nodes
        return
    assert (role, label) in nodes, f"{name}: falta ({role!r}, {label!r}) en {nodes}"


@pytest.mark.parametrize("name", STATIC)
def test_static_components_take_neither_focus_nor_clicks(name: str) -> None:
    clicks: list[int] = []
    after = button("Siguiente", lambda: clicks.append(1), key="end")
    pilot = _app(name, after=after).pilot()
    pilot.press("Tab")
    assert pilot.focused == "end", f"{name} entra en el orden de Tab"
    rect = next((pilot.rect(k) for k in ("x",) if pilot.rect(k)), None)
    if rect is not None:
        x, y, w, h = rect
        pilot.click_at(x + w / 2, y + h / 2)
        assert clicks == []


# Teclado de los componentes que no lo tenían probado en otro archivo.


def _key_of(pilot: Any, role: str, label: str) -> str:
    return next(n["key"] for n in pilot.a11y_tree() if n["role"] == role and n.get("label") == label)


def test_accordion_header_toggles_with_enter() -> None:
    open_: Signal[Any] = Signal(None)
    pilot = App(lambda: column()[accordion([("u", "Uno", text("contenido"))], open_, key="a")]).pilot()
    pilot.press("Tab")
    assert pilot.focused == _key_of(pilot, "button", "Uno")
    pilot.press("Enter")
    assert open_() == "u"
    pilot.press("Space")
    assert open_() is None


def test_switch_toggles_with_space_and_enter() -> None:
    on = Signal(False)
    pilot = App(lambda: column()[switch(on, "Wifi", key="s")]).pilot()
    pilot.press("Tab")
    pilot.press("Space")
    assert on() is True
    pilot.press("Enter")
    assert on() is False


@pytest.mark.parametrize("component", [radio, segmented])
def test_radio_groups_move_with_arrows(component: Callable[..., Any]) -> None:
    chosen = Signal("a")
    options = [("a", "Alfa"), ("b", "Beta"), ("c", "Gama")]
    pilot = App(lambda: column()[component(options, chosen, key="r")]).pilot()
    pilot.press("Tab")
    assert pilot.focused == "r-a"
    pilot.press("ArrowRight")
    assert chosen() == "b"
    pilot.press("ArrowLeft")
    pilot.press("ArrowLeft")
    assert chosen() == "c"  # da la vuelta
    pilot.press("Tab")  # Tab llega a otra opción, que se elige con Espacio
    pilot.press("Space")
    assert chosen() == pilot.focused.removeprefix("r-")


def test_slider_moves_with_arrows_and_clamps() -> None:
    value = Signal(0.5)
    pilot = App(lambda: column()[slider(value, key="s")]).pilot()
    pilot.press("Tab")
    pilot.press("ArrowRight")
    assert value() > 0.5
    for _ in range(40):
        pilot.press("ArrowLeft")
    assert value() == 0.0


def test_toast_close_button_works_from_the_keyboard() -> None:
    message: Signal[str | None] = Signal("Guardado")
    pilot = App(lambda: column()[toast(message, key="t")], motion=False).pilot()
    pilot.press("Tab")
    assert pilot.focused is not None
    pilot.press("Enter")
    pilot.settle()
    assert message() is None


def test_title_bar_buttons_stay_out_of_the_tab_order_but_answer_readers() -> None:
    # Como los botones de ventana del sistema: Tab no se para en ellos, pero un
    # lector de pantalla los pulsa.
    app = App(
        lambda: column(grow=1)[
            title_bar("Notas", controls="windows"), button("Guardar", lambda: None, key="b")
        ],
        size=(400, 160),
    )
    pilot = app.pilot()
    pilot.press("Tab")
    assert pilot.focused == "b"
    pilot.a11y_action("title-bar-maximize", "click")
    assert app.main.maximized is True


def test_table_headers_sort_from_the_keyboard() -> None:
    rows = [{"n": 2}, {"n": 1}, {"n": 3}]
    pilot = App(lambda: column()[table(rows, [Column("n", "N")], key="t")]).pilot()
    pilot.press("Tab")
    assert pilot.focused == "t/h/n"
    pilot.press("Enter")
    cells = [
        n.get("value") for n in pilot.a11y_tree() if n["role"] == "label" and n["key"].startswith("t/row")
    ]
    assert cells == ["1", "2", "3"]


def test_virtual_list_scrolls_with_page_keys() -> None:
    view = lambda: column()[
        virtual_list(200, lambda i: text(f"fila {i}"), item_height=30, key="v", height=150)
    ]
    pilot = App(view, size=(300, 200)).pilot()
    x, y, w, h = pilot.rect("v")
    pilot.move_to(x + w / 2, y + h / 2)
    pilot.press("PageDown")
    pilot.settle()
    assert pilot.scroll_offset("v")[1] > 0
    pilot.press("End")
    pilot.settle()
    labels = [n.get("value") for n in pilot.a11y_tree() if n["role"] == "label"]
    assert "fila 199" in labels


# La matriz. Cada celda es `archivo::prueba` o, si el aspecto no aplica, el motivo
# entre paréntesis. Las parametrizadas de arriba cubren render y accesibilidad de
# todos; aquí van las pruebas propias de cada uno.
R, A = (
    "test_coverage.py::test_component_renders_with_its_defaults",
    "test_coverage.py::test_component_announces_its_role_and_name",
)
STATIC_TEST = "test_coverage.py::test_static_components_take_neither_focus_nor_clicks"
NOT_INTERACTIVE = "(no es interactivo)"
LINKS_PENDING = "(pendiente para la 1.0: los enlaces no entran en el orden de Tab; un lector sí los pulsa)"

COVERAGE: dict[str, dict[str, str]] = {
    "accordion": {
        "pilot": "test_components.py::test_accordion_toggles_sections",
        "keyboard": "test_coverage.py::test_accordion_header_toggles_with_enter",
    },
    "avatar": {"render": "test_components.py::test_avatar_initials_and_stable_color", "pilot": STATIC_TEST},
    "badge": {"pilot": STATIC_TEST},
    "button": {
        "pilot": "test_pilot.py::test_click_runs_handler_and_rebuilds",
        "keyboard": "test_keyboard.py::test_enter_activates_focused_node",
    },
    "canvas": {
        "render": "test_canvas.py::test_figures_are_painted_at_their_coordinates",
        "pilot": "test_canvas.py::test_canvas_receives_clicks",
        "keyboard": "(la app lo da con `on_key`: el lienzo no tiene semántica propia)",
    },
    "card": {"pilot": STATIC_TEST},
    "chart": {
        "render": "test_charts.py::test_repaints_from_the_raster_cache_look_the_same",
        "pilot": "test_charts.py::test_zoom_with_a_descending_x",
        "keyboard": "(pendiente para la 1.0: el zoom solo va con rueda y arrastre)",
    },
    "checkbox": {
        "render": "test_components.py::test_checkbox_draws_mark_when_checked",
        "pilot": "test_components.py::test_checkbox_toggles_signal_with_click_and_keyboard",
        "a11y": "test_a11y.py::test_la_casilla_anuncia_su_estado_y_se_actualiza",
        "keyboard": "test_components.py::test_checkbox_toggles_signal_with_click_and_keyboard",
    },
    "color_picker": {
        "pilot": "test_pickers.py::test_color_picker_palette_and_hex_field",
        "a11y": "test_pickers.py::test_color_picker_announces_its_parts",
        "keyboard": "test_pickers.py::test_color_picker_square_and_hue_by_drag_and_keyboard",
    },
    "combobox": {
        "pilot": "test_pickers.py::test_combobox_filters_ignoring_case_and_accents",
        "keyboard": "test_pickers.py::test_combobox_keyboard_highlight_and_enter",
    },
    "date_picker": {
        "render": "test_pickers.py::test_pickers_render_selected_day_in_primary",
        "pilot": "test_pickers.py::test_date_picker_opens_on_the_value_month_and_chooses",
        "a11y": "test_pickers.py::test_date_picker_cells_announce_full_dates",
        "keyboard": "test_pickers.py::test_date_picker_keyboard_moves_days_weeks_and_months",
    },
    "dialog": {
        "pilot": "test_components.py::test_dialog_centers_the_card_and_takes_focus",
        "keyboard": "test_components.py::test_dialog_closes_with_escape",
    },
    "divider": {"render": "test_components.py::test_divider_horizontal_and_vertical", "pilot": STATIC_TEST},
    "field": {
        "pilot": "test_components.py::test_field_shows_label_and_error",
        "keyboard": "test_input.py::test_tab_leaves_the_field_and_space_types",
    },
    "markdown": {
        "pilot": "test_richtext.py::test_markdown_links_call_on_link_with_the_url",
        "keyboard": LINKS_PENDING,
    },
    "menu": {
        "pilot": "test_components.py::test_menu_opens_chooses_and_closes",
        "keyboard": "test_components.py::test_menu_closes_on_outside_click_and_escape",
    },
    "number_input": {
        "pilot": "test_pickers.py::test_number_input_typing_assigns_valid_numbers",
        "a11y": "test_pickers.py::test_number_input_is_a_spinbutton_for_screen_readers",
        "keyboard": "test_pickers.py::test_number_input_arrows_and_buttons_step_and_clamp",
    },
    "pages": {"pilot": "test_components.py::test_pages_switches_views"},
    "popover": {
        "render": "test_render.py::test_popover_paints_its_panel_where_it_was_placed",
        "pilot": "test_pilot.py::test_popover_flips_above_when_there_is_no_room_below",
        "keyboard": "test_pilot.py::test_popover_opens_below_and_closes_with_escape_or_outside_click",
    },
    "progress": {"pilot": STATIC_TEST},
    "radio": {
        "pilot": "test_components.py::test_radio_selects_one_option",
        "a11y": "test_a11y.py::test_el_grupo_de_radios_anuncia_posicion_y_seleccion",
        "keyboard": "test_coverage.py::test_radio_groups_move_with_arrows",
    },
    "rich_text": {
        "pilot": "test_richtext.py::test_link_spans_receive_clicks_and_are_announced_as_links",
        "keyboard": LINKS_PENDING,
    },
    "segmented": {
        "render": "test_components.py::test_segmented_thumb_slides",
        "pilot": "test_components.py::test_segmented_thumb_slides",
        "keyboard": "test_coverage.py::test_radio_groups_move_with_arrows",
    },
    "select": {
        "pilot": "test_components.py::test_select_opens_chooses_and_closes",
        "keyboard": "test_components.py::test_select_arrow_keys_change_value",
    },
    "skeleton": {
        "render": "test_components.py::test_skeleton_draws_lines_with_a_shorter_last",
        "pilot": STATIC_TEST,
    },
    "slider": {
        "pilot": "test_components.py::test_slider_drags_and_clamps",
        "a11y": "test_a11y.py::test_el_slider_anuncia_valor_y_rango",
        "keyboard": "test_coverage.py::test_slider_moves_with_arrows_and_clamps",
    },
    "sortable": {
        "render": "test_render.py::test_sortable_marks_where_the_item_will_land",
        "pilot": "test_pilot.py::test_sortable_reorders_with_the_pointer",
        "a11y": "test_a11y.py::test_sortable_is_a_list_and_announces_keyboard_moves",
        "keyboard": "test_pilot.py::test_sortable_keyboard_grab_move_drop_and_cancel",
    },
    "spinner": {"render": "test_components.py::test_spinner_pulses_and_never_rests", "pilot": STATIC_TEST},
    "splitter": {
        "render": "test_render.py::test_splitter_paints_a_divider_line_between_the_panes",
        "pilot": "test_pilot.py::test_splitter_drag_resizes_and_respects_both_minimums",
        "keyboard": "test_pilot.py::test_splitter_keyboard_and_screen_reader_actions",
    },
    "stat": {"pilot": STATIC_TEST},
    "switch": {
        "render": "test_components.py::test_switch_moves_knob",
        "pilot": "test_components.py::test_switch_moves_knob",
        "a11y": "test_a11y.py::test_el_interruptor_es_un_switch",
        "keyboard": "test_coverage.py::test_switch_toggles_with_space_and_enter",
    },
    "table": {
        "render": "test_table.py::test_renders_header_rows_and_stripes",
        "pilot": "test_table.py::test_clicking_a_header_cycles_ascending_descending_original",
        "keyboard": "test_coverage.py::test_table_headers_sort_from_the_keyboard",
    },
    "tabs": {
        "render": "test_components.py::test_tabs_underline_fades_between_tabs",
        "pilot": "test_components.py::test_tabs_click_and_arrow_keys",
        "keyboard": "test_components.py::test_tabs_click_and_arrow_keys",
    },
    "text_input": {
        "pilot": "test_input.py::test_enter_submits_single_line",
        "keyboard": "test_input.py::test_arrows_and_shift_select_then_typing_replaces",
    },
    "textarea": {
        "pilot": "test_input.py::test_textarea_newlines_vertical_moves_and_growth",
        "keyboard": "test_input.py::test_textarea_newlines_vertical_moves_and_growth",
    },
    "time_picker": {
        "pilot": "test_pickers.py::test_time_picker_lists_steps_and_chooses",
        "a11y": "test_pickers.py::test_time_picker_opens_with_the_value_in_view_and_announces_options",
        "keyboard": "test_pickers.py::test_time_picker_keyboard_limits_and_12_hour_format",
    },
    "title_bar": {
        "render": "test_render.py::test_title_bar_paints_the_window_buttons",
        "pilot": "test_pilot.py::test_title_bar_buttons_act_on_their_window",
        "a11y": "test_a11y.py::test_title_bar_buttons_are_named_buttons",
        "keyboard": "test_coverage.py::test_title_bar_buttons_stay_out_of_the_tab_order_but_answer_readers",
    },
    "toast": {
        "pilot": "test_components.py::test_toast_shows_dismisses_and_animates",
        "keyboard": "test_coverage.py::test_toast_close_button_works_from_the_keyboard",
    },
    "tooltip": {
        "pilot": "test_components.py::test_tooltip_appears_after_delay_and_hides_on_click",
        "keyboard": "(lo lleva el control que envuelve; el aviso es solo de puntero)",
    },
    "tree": {
        "render": "test_render.py::test_tree_highlights_the_selected_row_and_indents_children",
        "pilot": "test_pilot.py::test_tree_click_selects_and_chevron_expands",
        "a11y": "test_pilot.py::test_tree_announces_levels_positions_and_expansion",
        "keyboard": "test_pilot.py::test_tree_keyboard_follows_the_treeview_pattern",
    },
    "virtual_list": {
        "pilot": "test_virtual_list.py::test_scrolling_moves_the_visible_range",
        "keyboard": "test_coverage.py::test_virtual_list_scrolls_with_page_keys",
    },
}


def matrix() -> dict[str, dict[str, str]]:
    """`COVERAGE` con las pruebas comunes de este archivo rellenando los huecos."""
    full = {}
    for name in public_components():
        row = dict(COVERAGE.get(name, {}))
        row.setdefault("render", R)
        row.setdefault("a11y", A)
        row.setdefault("pilot", "")
        row.setdefault("keyboard", NOT_INTERACTIVE if name in STATIC else "")
        full[name] = row
    return full


def _test_source(ref: str) -> str | None:
    """El código de la prueba `archivo::nombre`, o `None` si no existe."""
    filename, _, test = ref.partition("::")
    path = TESTS / filename
    if not path.exists():
        return None
    src = path.read_text(encoding="utf-8")
    functions = {n.name: n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}
    node = functions.get(test)
    if node is None:
        return None
    # La prueba con sus decoradores y los helpers del archivo a los que llama (`_pilot()`…).
    called = {c.func.id for c in ast.walk(node) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    parts = [node, *node.decorator_list, *(functions[n] for n in called if n in functions and n != test)]
    return "\n".join(ast.get_source_segment(src, part) or "" for part in parts)


def test_every_public_component_is_in_the_gallery_and_the_matrix() -> None:
    names = public_components()
    assert sorted(GALLERY) == names, set(names) ^ set(GALLERY)
    assert set(ANNOUNCED) == set(GALLERY)
    assert set(COVERAGE) <= set(names), set(COVERAGE) - set(names)
    holes = [f"{name}.{aspect}" for name, row in matrix().items() for aspect, ref in row.items() if not ref]
    assert not holes, f"Sin prueba ni motivo: {holes}"


def test_every_reference_in_the_matrix_is_a_real_test_about_that_component() -> None:
    wrong = []
    for name, row in matrix().items():
        for aspect, ref in row.items():
            if ref.startswith("("):
                continue
            src = _test_source(ref)
            if src is None:
                wrong.append(f"{name}.{aspect}: no existe {ref}")
            elif ref.startswith("test_coverage.py::test_component_") or ref == STATIC_TEST:
                continue  # parametrizadas sobre `GALLERY`
            elif name not in src and name.replace("_", "") not in src:
                wrong.append(f"{name}.{aspect}: {ref} no usa {name}")
    assert not wrong, "\n".join(wrong)


def coverage_markdown() -> str:
    def cell(ref: str) -> str:
        if ref.startswith("("):
            return ref[1].upper() + ref[2:-1]
        filename, _, test = ref.partition("::")
        return f"`{filename.removesuffix('.py')}::{test.removeprefix('test_')}`"

    lines = [
        "# Cobertura por componente",
        "",
        "Cada componente público tiene una prueba de render, una de interacción con `Pilot`,",
        "una del árbol de accesibilidad (rol y nombre) y, si es interactivo, una de teclado.",
        "La tabla se genera desde `tests/test_coverage.py`, que comprueba que cada prueba",
        "existe y trata de ese componente; las comunes a todos están en ese mismo archivo:",
        "",
        "- `coverage::component_renders_with_its_defaults` pinta cada uno con sus valores por",
        "  defecto en el tema claro y en el oscuro;",
        "- `coverage::component_announces_its_role_and_name` busca su rol y su nombre en el árbol",
        "  de accesibilidad;",
        "- `coverage::static_components_take_neither_focus_nor_clicks` comprueba que los",
        "  decorativos no entran en el orden de Tab ni se quedan con los clics.",
        "",
        "| Componente | Render | Interacción | Accesibilidad | Teclado |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, row in matrix().items():
        cells = " | ".join(cell(row[a]) for a in ("render", "pilot", "a11y", "keyboard"))
        lines.append(f"| `{name}` | {cells} |")
    return "\n".join(lines) + "\n"


def test_coverage_page_is_up_to_date() -> None:
    current = coverage_markdown()
    if os.environ.get("AURORA_UPDATE_COVERAGE"):
        DOC.write_text(current, encoding="utf-8", newline="\n")
    assert DOC.read_text(encoding="utf-8") == current, (
        "docs/coverage.md no está al día: AURORA_UPDATE_COVERAGE=1 uv run pytest tests/test_coverage.py"
    )
