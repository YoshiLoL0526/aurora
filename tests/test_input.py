"""Campos de texto: escritura, cursor, selección, portapapeles, deshacer, IME y pintura."""

import sys

from test_render import _png_pixel

from aurora import App, Signal, box, column, scroll, text_input, textarea

# Saltar palabras: Alt en macOS, Ctrl en el resto.
WORD = "alt" if sys.platform == "darwin" else "ctrl"


def _form(value=None, *, size=(300, 120), **kw):
    value = value if value is not None else Signal("")
    view = lambda: column(padding=10, gap=10)[text_input(value, key="name", **kw)]
    pilot = App(view, size=size).pilot()
    return pilot, value


def test_typing_updates_the_signal():
    pilot, name = _form()
    pilot.click("name")
    assert pilot.focused == "name"
    pilot.type("Hola 👋🏽")
    assert name() == "Hola 👋🏽"
    assert pilot.selection("name") == (7, 7)  # el emoji con tono son 2 caracteres (code points)


def test_signal_changes_show_up_in_the_field():
    pilot, name = _form(Signal("viejo"))
    pilot.click("name")
    name.set("")
    pilot.frame()
    pilot.type("nuevo")
    assert name() == "nuevo"


def test_backspace_and_delete_respect_graphemes_and_words():
    pilot, name = _form()
    pilot.click("name")
    pilot.type("uno dos é")
    pilot.press("backspace")
    assert name() == "uno dos "
    pilot.press(f"{WORD}+backspace")
    assert name() == "uno "
    pilot.press("home")
    pilot.press("delete")
    assert name() == "no "


def test_arrows_and_shift_select_then_typing_replaces():
    pilot, name = _form(Signal("hola mundo"))
    pilot.click("name")
    pilot.press("end")
    pilot.press(f"{WORD}+shift+left")
    assert pilot.selection("name") == (5, 10)
    pilot.type("amigo")
    assert name() == "hola amigo"


def test_select_all_copy_cut_and_paste():
    pilot, name = _form(Signal("abc"))
    pilot.click("name")
    pilot.press("mod+a")
    pilot.press("mod+c")
    assert pilot.clipboard == "abc"
    pilot.press("end")
    pilot.press("mod+v")
    assert name() == "abcabc"
    pilot.press("mod+a")
    pilot.press("mod+x")
    assert name() == ""
    assert pilot.clipboard == "abcabc"


def test_pasting_newlines_into_single_line_input():
    pilot, name = _form()
    pilot.click("name")
    pilot.clipboard = "uno\r\ndos"
    pilot.press("mod+v")
    assert name() == "uno dos"


def test_undo_and_redo():
    pilot, name = _form()
    pilot.click("name")
    pilot.type("hola mundo")
    pilot.press("mod+z")
    assert name() == "hola "
    pilot.press("mod+z")
    assert name() == "hola"
    pilot.press("mod+shift+z")
    assert name() == "hola "


def test_enter_submits_single_line():
    sent = []
    pilot, name = _form(on_submit=sent.append)
    pilot.click("name")
    pilot.type("hola")
    pilot.press("enter")
    assert sent == ["hola"]
    assert name() == "hola"


def test_submit_handler_can_clear_the_field():
    msg = Signal("")
    sent = []

    def submit(text):
        sent.append(text)
        msg.set("")

    view = lambda: column()[text_input(msg, key="chat", on_submit=submit)]
    pilot = App(view, size=(300, 80)).pilot()
    pilot.click("chat")
    pilot.type("uno\n")
    pilot.type("dos\n")
    assert sent == ["uno", "dos"]
    assert msg() == ""


def test_controlled_value_without_on_change_does_not_change():
    view = lambda: column()[text_input("fijo", key="ro")]
    pilot = App(view, size=(300, 80)).pilot()
    pilot.click("ro")
    pilot.type("x")
    pilot.frame()
    pilot.press("end")
    assert pilot.selection("ro") == (4, 4)


def test_click_places_cursor_and_double_triple_click_select():
    pilot, _ = _form(Signal("hola mundo"))
    x, y, _w, h = pilot.rect("name")
    pilot.click_at(x + 14, y + h / 2)  # justo al principio del texto
    assert pilot.selection("name") == (0, 0)
    pilot.click_at(x + 14, y + h / 2)
    assert pilot.selection("name") == (0, 4)  # doble clic: palabra
    pilot.click_at(x + 14, y + h / 2)
    assert pilot.selection("name") == (0, 10)  # triple clic: todo


def test_drag_selects():
    pilot, _ = _form(Signal("hola mundo"))
    x, y, w, h = pilot.rect("name")
    pilot.move_to(x + 13, y + h / 2)
    pilot.mouse_down()
    pilot.move_to(x + w - 5, y + h / 2)
    pilot.mouse_up()
    assert pilot.selection("name") == (0, 10)


def test_tab_leaves_the_field_and_space_types():
    value = Signal("")
    view = lambda: column()[text_input(value, key="a"), text_input(Signal(""), key="b")]
    pilot = App(view, size=(300, 120)).pilot()
    pilot.press("tab")
    assert pilot.focused == "a"
    pilot.type("a b")
    assert value() == "a b"
    pilot.press("tab")
    assert pilot.focused == "b"


def test_on_key_runs_before_editing_and_can_block_it():
    value = Signal("")
    view = lambda: column(on_key=lambda e: e.key == "x")[text_input(value, key="f")]
    pilot = App(view, size=(300, 80)).pilot()
    pilot.click("f")
    pilot.type("axb")
    assert value() == "ab"


def test_ime_composition_and_commit():
    pilot, name = _form()
    pilot.click("name")
    pilot.type("a")
    pilot.ime_preedit("にほ")
    assert name() == "a"  # la composición no es parte del valor
    pilot.ime_commit("日本")
    assert name() == "a日本"


def test_textarea_newlines_vertical_moves_and_growth():
    value = Signal("")
    sent = []
    view = lambda: column()[textarea(value, key="t", rows=2, on_submit=sent.append)]
    pilot = App(view, size=(300, 300)).pilot()
    pilot.click("t")
    h2 = pilot.rect("t")[3]
    pilot.type("ab\ncd\nef")
    assert value() == "ab\ncd\nef"
    assert pilot.rect("t")[3] > h2  # tres líneas no caben en el mínimo de dos
    pilot.press("up")
    assert pilot.selection("t") == (5, 5)
    pilot.press("home")
    assert pilot.selection("t") == (3, 3)
    pilot.press("shift+end")
    assert pilot.selection("t") == (3, 5)
    pilot.press("mod+enter")
    assert sent == ["ab\ncd\nef"]


def test_long_text_scrolls_horizontally_to_keep_caret_visible(tmp_path):
    pilot, name = _form(size=(160, 60), width=120, color="#FF0000", bg="#000000", padding=(9, 12))
    pilot.click("name")
    pilot.type("x" * 60)
    assert name() == "x" * 60
    out = tmp_path / "long.png"
    pilot.png(str(out))
    x, y, w, h = pilot.rect("name")
    # El final del texto queda a la vista, pegado al borde derecho del contenido.
    assert _png_pixel(out, int(x + w - 15), int(y + h / 2))[0] > 100


def _caret_view(**kw):
    return lambda: column(bg="#000000", padding=10)[
        text_input(Signal(""), key="f", color="#FF0000", bg="#000000", border_width=0, **kw)
    ]


def test_caret_is_painted_when_focused(tmp_path):
    pilot = App(_caret_view(), size=(200, 60)).pilot()
    x, y, _w, h = pilot.rect("f")
    out = tmp_path / "caret.png"
    pilot.png(str(out))
    assert _png_pixel(out, int(x + 12), int(y + h / 2)) == (0, 0, 0)
    pilot.click("f")
    pilot.png(str(out))
    assert _png_pixel(out, int(x + 12), int(y + h / 2)) == (255, 0, 0)


def test_focus_ring_shows_on_click_for_inputs(tmp_path):
    view = lambda: column(bg="#000000", padding=20, focus_color="#00FF00")[
        text_input(Signal(""), key="f", bg="#000000", border_width=0)
    ]
    pilot = App(view, size=(260, 80)).pilot()
    pilot.click("f")
    pilot.settle()
    x, y, _w, h = pilot.rect("f")
    out = tmp_path / "ring.png"
    pilot.png(str(out))
    assert _png_pixel(out, int(x) - 3, int(y + h / 2)) == (0, 255, 0)


def test_placeholder_is_painted_only_when_empty(tmp_path):
    def render(value):
        view = lambda: box(bg="#000000", padding=10)[
            text_input(value, key="f", placeholder="████████", placeholder_color="#00FF00", bg="#000000")
        ]
        pilot = App(view, size=(260, 60)).pilot()
        out = tmp_path / "ph.png"
        pilot.png(str(out))
        x, y, _w, h = pilot.rect("f")
        return _png_pixel(out, int(x + 30), int(y + h / 2))

    assert render("")[1] > 150
    assert render("a")[1] < 50


def test_placeholder_starting_with_dollar_is_not_a_token():
    pilot, _ = _form(placeholder="$0.00")
    assert pilot.rect("name") is not None


def test_textarea_inside_scroll_keeps_caret_visible():
    notes = Signal("")
    view = lambda: column()[scroll(key="s", max_height=80)[textarea(notes, key="t")]]
    pilot = App(view, size=(300, 200)).pilot()
    pilot.click("t")
    pilot.type("\n".join(f"línea {i}" for i in range(12)))
    pilot.settle()
    assert pilot.scroll_offset("s")[1] > 0
    pilot.press("mod+home")
    pilot.settle()
    assert pilot.scroll_offset("s")[1] == 0
