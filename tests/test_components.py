"""Componentes: divider, avatar, checkbox, switch, tabs, tooltip y select."""

import pytest
from test_render import _png_pixel, _png_rows

from aurora import (
    App,
    Signal,
    accordion,
    animate,
    avatar,
    box,
    button,
    checkbox,
    column,
    dialog,
    divider,
    field,
    menu,
    pages,
    progress,
    radio,
    row,
    segmented,
    select,
    skeleton,
    slider,
    spinner,
    switch,
    tabs,
    text,
    text_input,
    toast,
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
    pilot.settle()  # el knob se desliza: se espera a que llegue
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


# --- movimiento por defecto ---------------------------------------------------


def _pixel(pilot, tmp_path, x, y):
    out = tmp_path / "px.png"
    pilot.png(str(out))
    return _png_pixel(out, int(x), int(y))


def test_switch_knob_slides_instead_of_jumping(tmp_path):
    state = Signal(False)
    view = lambda: column(bg="#000000", padding=10)[switch(state, key="sw")]
    pilot = App(view, size=(200, 50)).pilot()
    x, y, _w, h = pilot.rect("sw")
    axis = int(y + h / 2)
    white = (255, 255, 255)
    assert _pixel(pilot, tmp_path, x + 8, axis) == white  # el knob empieza a la izquierda
    assert _pixel(pilot, tmp_path, x + 30, axis) != white

    pilot.click("sw")
    pilot.frame(0.09)  # a mitad del deslizamiento (0.18 s)
    # Ni en el origen ni en el destino: se está moviendo.
    assert _pixel(pilot, tmp_path, x + 8, axis) != white
    assert _pixel(pilot, tmp_path, x + 30, axis) != white

    pilot.settle()
    assert _pixel(pilot, tmp_path, x + 8, axis) != white
    assert _pixel(pilot, tmp_path, x + 30, axis) == white


def test_switch_jumps_with_motion_off(tmp_path):
    state = Signal(False)
    view = lambda: column(bg="#000000", padding=10)[switch(state, key="sw")]
    pilot = App(view, size=(200, 50), motion=False).pilot()
    x, y, _w, h = pilot.rect("sw")
    axis = int(y + h / 2)
    pilot.click("sw")
    # Sin animación el knob ya está en el destino en el mismo frame del clic.
    assert _pixel(pilot, tmp_path, x + 30, axis) == (255, 255, 255)
    assert _pixel(pilot, tmp_path, x + 8, axis) != (255, 255, 255)


def test_motion_env_var_disables_component_animation(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_MOTION", "0")
    state = Signal(False)
    view = lambda: column(bg="#000000", padding=10)[switch(state, key="sw")]
    pilot = App(view, size=(200, 50)).pilot()
    x, y, _w, h = pilot.rect("sw")
    axis = int(y + h / 2)
    pilot.click("sw")
    assert _pixel(pilot, tmp_path, x + 30, axis) == (255, 255, 255)


def test_checkbox_mark_enters_and_leaves_with_motion(tmp_path):
    done = Signal(True)
    view = lambda: column(bg="#000000", padding=10)[checkbox(done, key="cb")]
    pilot = App(view, size=(100, 50)).pilot()
    x, y, _w, h = pilot.rect("cb")
    center = (x + 9, y + h / 2)
    assert sum(_pixel(pilot, tmp_path, *center)) > 500  # la marca ya está (sin volver a entrar)

    pilot.click("cb")
    assert done() is False
    pilot.frame(0.02)
    assert sum(_pixel(pilot, tmp_path, *center)) > 150  # sale desvaneciéndose, aún se ve
    pilot.settle()
    assert sum(_pixel(pilot, tmp_path, *center)) < 100  # y se va del todo

    pilot.click("cb")
    pilot.settle()
    assert sum(_pixel(pilot, tmp_path, *center)) > 500  # al volver, entra con el mismo efecto


def test_tabs_underline_fades_between_tabs(tmp_path):
    page = Signal("a")
    view = lambda: column(bg="#000000")[tabs([("a", "Uno"), ("b", "Dos")], page, key="t")]
    pilot = App(view, size=(300, 80)).pilot()
    xa, ya, wa, ha = pilot.rect("t-a")
    xb, yb, wb, hb = pilot.rect("t-b")
    purple, black = (124, 92, 255), (0, 0, 0)
    under = (xa + wa / 2, ya + ha - 1)

    assert _pixel(pilot, tmp_path, *under) == purple
    pilot.click("t-b")
    pilot.frame(0.04)
    mid = _pixel(pilot, tmp_path, *under)
    assert mid not in (black, purple)  # ni encendido ni apagado: fundiéndose
    pilot.settle()
    assert _pixel(pilot, tmp_path, *under) == black
    assert _pixel(pilot, tmp_path, xb + wb / 2, yb + hb - 1) == purple


def test_select_menu_slides_in_and_fades_out(tmp_path):
    lang = Signal("es")
    view = lambda: column(padding=10, bg="#000000")[
        select(lang, [("es", "Español"), ("en", "English")], key="lang")
    ]
    pilot = App(view, size=(300, 300)).pilot()
    x, y = pilot.rect("lang")[:2]
    point = (x + 8, y + 54)  # dentro del panel, lejos del borde y de las opciones

    pilot.click("lang")
    assert _pixel(pilot, tmp_path, *point) == (0, 0, 0)  # acaba de entrar: aún invisible
    pilot.frame(0.06)
    chosen = (26, 31, 46)  # $surface_hover: la opción activa
    mid = _pixel(pilot, tmp_path, *point)
    assert mid not in ((0, 0, 0), chosen)  # a medio aparecer
    pilot.settle()
    assert _pixel(pilot, tmp_path, *point) == chosen

    pilot.press("escape")
    pilot.frame(0.02)
    assert _pixel(pilot, tmp_path, *point) != (0, 0, 0)  # la instantánea se desvanece
    pilot.settle()
    assert _pixel(pilot, tmp_path, *point) == (0, 0, 0)


# --- progreso ---------------------------------------------------------------


def test_progress_bar_animates_to_its_new_value(tmp_path):
    value = Signal(0.25)
    view = lambda: column(padding=10, bg="#000000")[progress(value, key="p", width=100)]
    pilot = App(view, size=(200, 50)).pilot()
    purple, rail = (124, 92, 255), (26, 31, 46)  # $primary y $surface_hover
    assert _pixel(pilot, tmp_path, 30, 14) == purple  # el 25 % de 100 px
    assert _pixel(pilot, tmp_path, 40, 14) == rail

    value.set(0.75)
    pilot.frame()  # el primer frame pinta el valor anterior
    assert _pixel(pilot, tmp_path, 40, 14) == rail
    pilot.frame(0.09)  # a mitad del crecimiento (0.18 s)
    assert _pixel(pilot, tmp_path, 40, 14) == purple
    assert _pixel(pilot, tmp_path, 70, 14) == rail  # aún no llega al 75 %
    pilot.settle()
    assert _pixel(pilot, tmp_path, 80, 14) == purple
    assert _pixel(pilot, tmp_path, 95, 14) == rail


def test_progress_clamps_and_scales_by_max(tmp_path):
    value = Signal(3.0)

    def view():
        return column(padding=10, bg="#000000")[progress(value, max=10, color="$success", key="p", width=100)]

    pilot = App(view, size=(200, 50)).pilot()
    success, rail = (52, 211, 153), (26, 31, 46)  # $success y $surface_hover
    assert _pixel(pilot, tmp_path, 35, 14) == success  # 3 de 10
    assert _pixel(pilot, tmp_path, 50, 14) == rail
    value.set(12.0)  # por encima de max: el carril se llena
    pilot.settle()
    assert _pixel(pilot, tmp_path, 105, 14) == success


def test_progress_rejects_max_not_positive():
    with pytest.raises(ValueError, match="positivo"):
        progress(1, max=0)


# --- diálogo ------------------------------------------------------------------


def _dialog_app(**kwargs):
    open_ = Signal(True)
    closes: list[int] = []
    view = lambda: box(bg="#FFFFFF")[
        dialog(
            open_,
            box(width=100, height=40, bg="#000000", key="body"),
            on_close=lambda: closes.append(1),
            key="dlg",
            width=200,
            **kwargs,
        )
    ]
    return App(view, size=(300, 200)).pilot(), open_, closes


def test_dialog_centers_the_card_and_takes_focus():
    pilot, _open, _closes = _dialog_app()
    assert pilot.rect("dlg") == (0, 0, 300, 200)  # fondo a pantalla completa
    # La tarjeta toma el foco al abrirse (el contenido no trae `autofocus`).
    assert pilot.focused == "dlg/0"
    x, y, _w, h = pilot.rect("dlg/0")
    assert (x, y) == (50, 55)
    assert h == 90  # 40 del contenido + 24 de relleno por arriba y por abajo + 1 de borde por lado


def test_dialog_closes_on_outside_click():
    pilot, open_, closes = _dialog_app()
    pilot.click("body")
    assert open_() is True and closes == []  # dentro no cierra (capture)
    pilot.click_at(10, 100)  # fuera de la tarjeta
    assert open_() is False and closes == [1]


def test_dialog_closes_with_escape():
    pilot, open_, closes = _dialog_app()
    pilot.press("escape")
    assert open_() is False and closes == [1]


def test_dialog_content_autofocus_wins():
    open_ = Signal(True)
    view = lambda: box(bg="#FFFFFF")[
        dialog(open_, column(padding=8)[text_input("", autofocus=True, key="field")], key="dlg", width=200)
    ]
    pilot = App(view, size=(300, 200)).pilot()
    # El campo del contenido pide el foco: la tarjeta no se lo quita.
    assert pilot.focused == "field"


def test_dialog_backdrop_fades_in(tmp_path):
    open_ = Signal(False)

    def view():
        return box(bg="#FFFFFF")[dialog(open_, box(width=40, height=20, bg="#000000"), key="dlg", width=120)]

    pilot = App(view, size=(300, 200)).pilot()
    open_.set(True)
    pilot.frame()
    point = (10, 100)
    assert _pixel(pilot, tmp_path, *point) == (255, 255, 255)  # acaba de entrar: aún transparente
    pilot.frame(0.06)
    mid = _pixel(pilot, tmp_path, *point)
    assert mid not in ((255, 255, 255), (85, 85, 85))  # a medio oscurecer
    pilot.settle()
    assert _pixel(pilot, tmp_path, *point) == (85, 85, 85)  # #000000AA sobre blanco


# --- toast --------------------------------------------------------------------


def test_toast_shows_dismisses_and_animates(tmp_path):
    message = Signal("Guardado")
    view = lambda: box(bg="#000000")[toast(message, key="t")]
    pilot = App(view, size=(400, 200)).pilot()
    x, y, w, h = pilot.rect("t")
    point = (int(x + w / 2), int(y + h / 2))
    assert _pixel(pilot, tmp_path, *point) != (0, 0, 0)  # visible

    pilot.click("t")
    assert message() is None
    assert pilot.rect("t") is None
    pilot.settle()

    message.set("Otra vez")
    pilot.frame()
    x, y, w, h = pilot.rect("t")
    point = (int(x + w / 2), int(y + h / 2))
    # El primer frame está en el origen de la entrada: desplazado y transparente.
    assert _pixel(pilot, tmp_path, *point) == (0, 0, 0)
    pilot.settle()
    assert _pixel(pilot, tmp_path, *point) != (0, 0, 0)


def test_pulse_validation():
    with pytest.raises(ValueError, match="positiva"):
        animate.pulse(0)
    with pytest.raises(ValueError, match="floor"):
        animate.pulse(floor=1.5)
    with pytest.raises(ValueError, match="pulse debe ser"):
        App(lambda: box(width=10, height=10, pulse=animate.tween(0.3)), size=(40, 40)).pilot()


# --- páginas -------------------------------------------------------------------


def test_pages_switches_views():
    current = Signal("uno")
    views = {
        "uno": lambda: column(gap=60)[[text(f"Uno {i}", key=f"u{i}") for i in range(20)]],
        "dos": lambda: column(gap=60)[text("Dos", key="d0")],
    }
    pilot = App(lambda: pages(current, views, key="pg"), size=(300, 200)).pilot()
    assert pilot.rect("u0") is not None
    assert pilot.rect("d0") is None

    pilot.scroll("pg-uno", 120)
    assert pilot.scroll_offset("pg-uno") == (0.0, 120.0)
    current.set("dos")
    pilot.settle()
    assert pilot.rect("u0") is None
    assert pilot.rect("d0") is not None
    # Al desaparecer la página se suelta su scroll...
    assert pilot.scroll_offset("pg-uno") is None
    # ...y al volver, empieza arriba.
    current.set("uno")
    pilot.settle()
    assert pilot.scroll_offset("pg-uno") == (0.0, 0.0)


def test_pages_rejects_unknown_values():
    with pytest.raises(ValueError, match="no hay vista"):
        pages(Signal("x"), {"a": lambda: text("A")})


# --- radio, segmented, slider, spinner y esqueleto ----------------------------


def test_radio_selects_one_option(tmp_path):
    choice = Signal("a")
    view = lambda: column(bg="#000000", padding=10)[radio([("a", "Uno"), ("b", "Dos")], choice, key="r")]
    pilot = App(view, size=(200, 100)).pilot()
    x, y, _w, h = pilot.rect("r-b")
    center = (int(x + 9), int(y + h / 2))  # el círculo de "Dos"
    assert _pixel(pilot, tmp_path, *center) != (255, 255, 255)
    pilot.click("r-b")
    assert choice() == "b"
    pilot.settle()
    assert _pixel(pilot, tmp_path, *center) == (255, 255, 255)  # el punto blanco entró


def test_segmented_thumb_slides(tmp_path):
    choice = Signal("a")
    view = lambda: column(bg="#000000", padding=10)[
        segmented([("a", "Uno"), ("b", "Dos")], choice, key="seg")
    ]
    pilot = App(view, size=(260, 60)).pilot()
    xa, ya, wa, ha = pilot.rect("seg-a")
    axis = int(ya + ha / 2)
    edge = (int(xa + 4), axis)  # borde izquierdo de la ranura a (sin texto)
    middle = (int(xa + wa + 2), axis)  # lado izquierdo de la ranura b
    thumb = (19, 23, 34)  # $surface
    assert _pixel(pilot, tmp_path, *edge) == thumb
    assert _pixel(pilot, tmp_path, *middle) != thumb

    choice.set("b")
    pilot.frame()
    pilot.frame(0.09)  # a mitad del deslizamiento (0.18 s)
    assert _pixel(pilot, tmp_path, *edge) != thumb  # ya se fue de su ranura
    assert _pixel(pilot, tmp_path, *middle) == thumb  # y está pasando por el medio
    pilot.settle()
    assert _pixel(pilot, tmp_path, *edge) != thumb
    assert _pixel(pilot, tmp_path, *middle) == thumb


def test_slider_fill_and_thumb_follow_the_value(tmp_path):
    value = Signal(0.5)
    view = lambda: column(bg="#000000", padding=10)[slider(value, key="sl", width=180)]
    pilot = App(view, size=(220, 60)).pilot()
    axis = int(pilot.rect("sl")[1] + 12)  # centro del carril
    assert _pixel(pilot, tmp_path, 60, axis) == (124, 92, 255)  # relleno
    assert _pixel(pilot, tmp_path, 100, axis) == (255, 255, 255)  # centro del pulgar
    assert _pixel(pilot, tmp_path, 200, axis) == (0, 0, 0)  # más allá del carril


def test_slider_drags_and_clamps():
    value = Signal(0.0)
    view = lambda: column(padding=10)[slider(value, key="sl", width=180)]
    pilot = App(view, size=(220, 60)).pilot()
    pilot.drag("sl", dx=82, steps=4)  # 82 px de 164: la mitad
    assert value() == pytest.approx(0.5, abs=0.01)
    pilot.drag("sl", dx=500, steps=2)
    assert value() == 1.0
    pilot.drag("sl", dx=-500, steps=2)
    assert value() == 0.0


def test_slider_rejects_max_not_greater_than_min():
    with pytest.raises(ValueError, match="mayor"):
        slider(Signal(0.5), min=1, max=1)


def test_spinner_pulses_and_never_rests(tmp_path):
    view = lambda: column(bg="#000000", padding=10)[spinner(key="s")]
    pilot = App(view, size=(120, 60)).pilot()
    x, y, _w, h = pilot.rect("s")
    dot = (int(x + 4), int(y + h / 2))
    assert _pixel(pilot, tmp_path, *dot) == (124, 92, 255)  # nace a opacidad plena
    assert pilot.frame() is True  # el vaivén nunca termina
    pilot.frame(0.5)
    dim = _pixel(pilot, tmp_path, *dot)
    assert 0 < sum(dim) < sum((124, 92, 255))  # atenuado, sin apagarse


def test_spinner_is_static_with_motion_off(tmp_path):
    view = lambda: column(bg="#000000", padding=10)[spinner(key="s")]
    pilot = App(view, size=(120, 60), motion=False).pilot()
    x, y, _w, h = pilot.rect("s")
    dot = (int(x + 4), int(y + h / 2))
    assert pilot.frame() is False  # sin vaivén no queda trabajo pendiente
    pilot.frame(0.7)
    assert _pixel(pilot, tmp_path, *dot) == (124, 92, 255)


def test_skeleton_draws_lines_with_a_shorter_last(tmp_path):
    view = lambda: column(width=200, bg="#000000")[skeleton(lines=2, height=10, gap=6)]
    pilot = App(view, size=(220, 60)).pilot()
    block = (26, 31, 46)  # $surface_hover
    assert _pixel(pilot, tmp_path, 100, 5) == block  # primera línea, ancho completo
    assert _pixel(pilot, tmp_path, 100, 21) == block  # segunda línea (hasta el 60 %)
    assert _pixel(pilot, tmp_path, 150, 21) == (0, 0, 0)


# --- field, menú y acordeón ----------------------------------------------------


def _brightest(path, y):
    """Color más intenso de la fila: el trazo de un glifo, libre de antialiasing."""
    channels, rows = _png_rows(path, y + 1)
    row = rows[y]
    return max(
        (tuple(row[x * channels : x * channels + 3]) for x in range(len(row) // channels)),
        key=sum,
    )


def test_field_shows_label_and_error(tmp_path):
    view = lambda: column(bg="#000000", padding=10)[
        field(box(width=120, height=20, bg="#222222", key="ctl"), label="Correo", error="Inválido")
    ]
    pilot = App(view, size=(200, 120)).pilot()
    _x, y, _w, h = pilot.rect("ctl")
    out = tmp_path / "field.png"
    pilot.png(str(out))
    # La etiqueta va encima del control.
    assert any(_brightest(out, row) != (0, 0, 0) for row in range(int(y) - 16, int(y) - 2))
    # El error va debajo, en color de peligro.
    below = [_brightest(out, row) for row in range(int(y + h) + 6, int(y + h) + 16)]
    assert any(r > 120 and r > g and r > b for r, g, b in below)


def test_menu_opens_chooses_and_closes():
    actions = []
    view = lambda: column(padding=10, bg="#000000")[
        menu(
            button("Acciones", variant="soft", key="trigger"),
            [
                ("Editar", lambda: actions.append("editar")),
                ("Borrar", lambda: actions.append("borrar"), {"color": "$danger"}),
            ],
            key="m",
        )
    ]
    pilot = App(view, size=(240, 200)).pilot()
    assert pilot.rect("m-item-0") is None
    pilot.click("trigger")
    assert pilot.rect("m-item-0") is not None
    pilot.click("m-item-1")
    assert actions == ["borrar"]
    assert pilot.rect("m-item-0") is None


def test_menu_closes_on_outside_click_and_escape():
    view = lambda: column(padding=10, bg="#000000")[
        menu(button("Menú", key="t2"), [("Uno", lambda: None)], key="m2")
    ]
    pilot = App(view, size=(240, 220)).pilot()
    pilot.click("t2")
    assert pilot.rect("m2-item-0") is not None
    pilot.click_at(230, 210)
    assert pilot.rect("m2-item-0") is None

    pilot.click("t2")
    pilot.press("escape")
    assert pilot.rect("m2-item-0") is None


def test_accordion_toggles_sections(tmp_path):
    open_ = Signal(None)
    view = lambda: column(padding=10, bg="#000000", width=240)[
        accordion(
            [
                ("uno", "Uno", box(height=30, bg="#00FF00", key="c1")),
                ("dos", "Dos", box(height=30, bg="#0000FF", key="c2")),
            ],
            open_,
            key="acc",
        )
    ]
    pilot = App(view, size=(280, 220)).pilot()
    x, y, _w, _h = pilot.rect("c1")
    point = (int(x + 10), int(y + 10))
    assert _pixel(pilot, tmp_path, *point) == (0, 0, 0)  # plegado: el contenido está recortado

    pilot.click("acc-uno")
    assert open_() == "uno"
    pilot.frame()
    pilot.frame(0.02)
    assert _pixel(pilot, tmp_path, *point) == (0, 0, 0)  # aún no ha llegado (despliegue animado)
    pilot.settle()
    assert _pixel(pilot, tmp_path, *point) == (0, 255, 0)  # desplegado

    pilot.click("acc-dos")  # exclusivo: abre una y pliega la otra
    assert open_() == "dos"
    pilot.settle()
    assert _pixel(pilot, tmp_path, *point) == (0, 0, 0)
    pilot.click("acc-dos")  # pulsar la abierta la pliega
    assert open_() is None
