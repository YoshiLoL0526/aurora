"""Componentes: divider, avatar, checkbox, switch, tabs, tooltip y select."""

from test_render import _png_pixel

from aurora import (
    App,
    Signal,
    avatar,
    box,
    button,
    checkbox,
    column,
    divider,
    row,
    select,
    switch,
    tabs,
    text,
    tooltip,
)

# --- divider y avatar -------------------------------------------------------


def test_divider_horizontal_and_vertical():
    view = lambda: column()[
        divider(key="h"),
        row(height=40)[box(width=10), divider(vertical=True, key="v"), box(width=10)],
    ]
    pilot = App(view, size=(200, 100)).pilot()
    assert pilot.rect("h") == (0, 0, 200, 1)
    assert pilot.rect("v")[2:] == (1, 40)


def test_avatar_initials_and_stable_color():
    a = avatar("Ada Lovelace", size=40)
    assert a.children[0].content == "AL"
    assert a.style["bg"] == avatar("Ada Lovelace").style["bg"]
    assert avatar("").children[0].content == "?"


def test_avatar_with_image(tmp_path):
    from aurora import MIDNIGHT, _core

    src = tmp_path / "face.png"
    _core.render_png(box(bg="#00FF00").to_spec(MIDNIGHT), 20, 10, str(src), 1.0)
    pilot = App(lambda: column()[avatar("X", src=src, size=48, key="a")], size=(100, 100)).pilot()
    assert pilot.rect("a")[2:] == (48, 48)


# --- checkbox y switch ------------------------------------------------------


def test_checkbox_toggles_signal_with_click_and_keyboard():
    done = Signal(False)
    changes = []
    view = lambda: column()[checkbox(done, "Hecho", key="cb", on_change=changes.append)]
    pilot = App(view, size=(200, 60)).pilot()
    pilot.click("cb")
    assert done() is True
    pilot.press("space")
    assert done() is False
    pilot.press("enter")
    assert done() is True
    assert changes == [True, False, True]


def test_checkbox_draws_mark_when_checked(tmp_path):
    def center_pixel(value):
        view = lambda: column(bg="#000000", padding=10)[checkbox(value, key="cb")]
        pilot = App(view, size=(100, 50)).pilot()
        out = tmp_path / "cb.png"
        pilot.png(str(out))
        x, y, _w, h = pilot.rect("cb")
        return _png_pixel(out, int(x + 9), int(y + h / 2))

    off, on = center_pixel(False), center_pixel(True)
    assert off != on


def test_switch_moves_knob(tmp_path):
    state = Signal(False)
    view = lambda: column(bg="#000000", padding=10)[switch(state, "Wi-Fi", key="sw")]
    pilot = App(view, size=(200, 50)).pilot()
    out = tmp_path / "sw.png"
    x, y, _w, h = pilot.rect("sw")
    knob_off, knob_on = (int(x + 10), int(y + h / 2)), (int(x + 26), int(y + h / 2))
    pilot.png(str(out))
    assert _png_pixel(out, *knob_off) == (255, 255, 255)
    pilot.click("sw")
    assert state() is True
    pilot.png(str(out))
    assert _png_pixel(out, *knob_on) == (255, 255, 255)
    assert _png_pixel(out, *knob_off) != (255, 255, 255)


# --- tabs -------------------------------------------------------------------


def test_tabs_click_and_arrow_keys():
    page = Signal("a")
    view = lambda: column()[tabs([("a", "Uno"), ("b", "Dos"), ("c", "Tres")], page, key="t")]
    pilot = App(view, size=(300, 80)).pilot()
    pilot.click("t-b")
    assert page() == "b"
    pilot.press("right")
    assert page() == "c"
    pilot.press("right")
    assert page() == "a"  # vuelve al principio
    pilot.press("left")
    assert page() == "c"


# --- tooltip ----------------------------------------------------------------


def _tip_view():
    return column(padding=20, bg="#000000", tooltip_bg="#FF0000", tooltip_color="#FFFFFF")[
        tooltip(button("Guardar", lambda: None, key="save"), "Guarda los cambios"),
        text("sin ayuda", key="plain"),
    ]


def test_tooltip_appears_after_delay_and_hides_on_click(tmp_path):
    pilot = App(_tip_view, size=(300, 200)).pilot()
    x, y, w, h = pilot.rect("save")
    pilot.move_to(x + w / 2, y + h / 2)
    assert pilot.tooltip is None
    pilot.frame(dt=0.3)
    assert pilot.tooltip is None  # todavía no
    pilot.frame(dt=0.3)
    assert pilot.tooltip == "Guarda los cambios"
    pilot.settle()
    out = tmp_path / "tip.png"
    pilot.png(str(out))
    # La burbuja aparece debajo del botón.
    assert _png_pixel(out, int(x + w / 2), int(y + h + 14)) == (255, 0, 0)
    pilot.mouse_down()
    assert pilot.tooltip is None
    pilot.mouse_up()


def test_visible_tooltip_does_not_break_later_frames(tmp_path):
    pilot = App(_tip_view, size=(300, 200)).pilot()
    x, y, w, h = pilot.rect("save")
    pilot.move_to(x + w / 2, y + h / 2)
    pilot.frame(dt=0.6)
    for _ in range(30):  # varios frames con la burbuja visible
        pilot.frame()
    out = tmp_path / "frames.png"
    pilot.png(str(out))
    assert _png_pixel(out, int(x + 4), int(y + h / 2)) != (0, 0, 0)  # el botón se sigue viendo


def test_tooltip_resets_when_pointer_moves_to_another_node():
    pilot = App(_tip_view, size=(300, 200)).pilot()
    x, y, _w, _h = pilot.rect("save")
    pilot.move_to(x + 5, y + 5)
    pilot.frame(dt=0.6)
    assert pilot.tooltip is not None
    px, py, _pw, ph = pilot.rect("plain")
    pilot.move_to(px + 2, py + ph / 2)
    assert pilot.tooltip is None
    pilot.leave()
    assert pilot.tooltip is None


def test_tooltip_on_any_element_via_style():
    view = lambda: column(padding=10)[box(key="b", width=40, height=40, tooltip="Hola")]
    pilot = App(view, size=(200, 200)).pilot()
    pilot.move_to(30, 30)
    pilot.frame(dt=1.0)
    assert pilot.tooltip == "Hola"


# --- select -----------------------------------------------------------------


def _select_app(value, below_clicks=None, **kw):
    clicks = below_clicks if below_clicks is not None else []
    view = lambda: column(padding=10, gap=10)[
        select(value, [("es", "Español"), ("en", "English"), ("fr", "Français")], key="lang", **kw),
        button("Debajo", lambda: clicks.append(1), key="below"),
    ]
    return App(view, size=(300, 300)).pilot()


def test_select_opens_chooses_and_closes():
    lang = Signal("es")
    pilot = _select_app(lang)
    assert pilot.rect("lang-opt-1") is None
    pilot.click("lang")
    assert pilot.rect("lang-opt-1") is not None
    pilot.click("lang-opt-1")
    assert lang() == "en"
    assert pilot.rect("lang-opt-1") is None


def test_select_menu_is_above_later_siblings():
    lang, below = Signal("es"), []
    pilot = _select_app(lang, below)
    pilot.click("lang")
    # La lista tapa el botón de debajo: el clic llega a una opción, no al botón.
    bx, by, bw, bh = pilot.rect("below")
    pilot.click_at(bx + bw / 2, by + bh / 2)
    assert below == []
    assert pilot.rect("lang-opt-0") is None  # se eligió una opción y se cerró


def test_select_closes_on_outside_click_and_escape():
    lang = Signal("es")
    pilot = _select_app(lang)
    pilot.click("lang")
    pilot.click_at(290, 290)
    assert pilot.rect("lang-opt-0") is None
    assert lang() == "es"
    pilot.click("lang")
    pilot.press("escape")
    assert pilot.rect("lang-opt-0") is None


def test_select_arrow_keys_change_value():
    lang = Signal("es")
    pilot = _select_app(lang)
    pilot.focus("lang")
    pilot.press("down")
    assert lang() == "en"
    pilot.press("down")
    pilot.press("down")
    assert lang() == "fr"  # no pasa del último
    pilot.press("up")
    assert lang() == "en"


def test_select_placeholder_without_value():
    lang = Signal(None)
    pilot = _select_app(lang, placeholder="Idioma")
    assert pilot.rect("lang") is not None
