"""Teclado y foco: Tab, activación, on_key, anillo de foco y desplazamiento con teclas."""

import pytest
from test_render import _png_pixel

from aurora import App, Signal, box, button, column, row, scroll


def _buttons(clicks=None, **root_style):
    def cb(name):
        return (lambda: clicks.append(name)) if clicks is not None else (lambda: None)

    return lambda: row(gap=10, padding=10, **root_style)[
        button("A", cb("a"), key="a"),
        button("B", cb("b"), key="b"),
        button("C", cb("c"), key="c"),
    ]


def test_tab_cycles_in_paint_order_and_wraps():
    pilot = App(_buttons(), size=(300, 80)).pilot()
    assert pilot.focused is None
    seen = []
    for _ in range(4):
        pilot.press("tab")
        seen.append(pilot.focused)
    assert seen == ["a", "b", "c", "a"]
    pilot.press("shift+tab")
    assert pilot.focused == "c"


def test_enter_activates_focused_node():
    clicks = []
    pilot = App(_buttons(clicks), size=(300, 80)).pilot()
    pilot.press("tab")
    pilot.press("tab")
    pilot.press("enter")
    assert clicks == ["b"]


def test_space_activates_on_release():
    clicks = []
    pilot = App(_buttons(clicks), size=(300, 80)).pilot()
    pilot.focus("a")
    pilot.key_down("space")
    assert clicks == []
    pilot.key_up("space")
    assert clicks == ["a"]


def test_click_focuses_and_clicking_empty_space_blurs():
    pilot = App(_buttons(), size=(300, 80)).pilot()
    pilot.click("b")
    assert pilot.focused == "b"
    pilot.click_at(290, 70)
    assert pilot.focused is None


def _ring_pixel(pilot, tmp_path, key):
    x, y, _w, h = pilot.rect(key)
    pilot.settle()
    out = tmp_path / "ring.png"
    pilot.png(str(out))
    return _png_pixel(out, int(x) - 3, int(y + h / 2))


def test_focus_ring_only_with_keyboard(tmp_path):
    # Cajas planas: la sombra de `button` teñiría el píxel del anillo.
    view = lambda: row(gap=20, padding=20, bg="#000000", focus_color="#FF0000")[
        box(key="a", width=40, height=30, on_click=lambda: None),
        box(key="b", width=40, height=30, on_click=lambda: None),
    ]
    pilot = App(view, size=(300, 80)).pilot()
    pilot.click("a")
    assert _ring_pixel(pilot, tmp_path, "a") == (0, 0, 0)  # clic: sin anillo
    pilot.press("tab")
    pilot.press("shift+tab")
    assert pilot.focused == "a"
    assert _ring_pixel(pilot, tmp_path, "a") == (255, 0, 0)


def test_focus_and_blur_handlers():
    log = []
    view = lambda: row()[
        box(key="x", width=20, height=20, focusable=True, on_focus=lambda: log.append("+x")),
        box(key="y", width=20, height=20, focusable=True, on_blur=lambda: log.append("-y")),
    ]
    pilot = App(view, size=(100, 40)).pilot()
    pilot.press("tab")
    pilot.press("tab")
    pilot.press("tab")
    assert log == ["+x", "-y", "+x"]  # el tercer Tab vuelve al principio


def test_focusable_overrides_default():
    view = lambda: row()[
        button("no", lambda: None, key="skip", focusable=False),
        box(key="panel", width=20, height=20, focusable=True),
    ]
    pilot = App(view, size=(200, 40)).pilot()
    pilot.press("tab")
    assert pilot.focused == "panel"


def test_on_key_bubbles_from_focus_to_ancestors():
    events = []
    view = lambda: column(on_key=lambda e: events.append(e.key))[button("A", lambda: None, key="a")]
    pilot = App(view, size=(100, 60)).pilot()
    pilot.press("x")  # sin foco: la recibe la raíz
    pilot.focus("a")
    pilot.press("y")  # con foco: sube desde el botón hasta la raíz
    assert events == ["x", "y"]


def test_returning_true_consumes_the_key():
    view = lambda: row(on_key=lambda e: e.key == "Tab")[
        button("A", lambda: None, key="a"),
        button("B", lambda: None, key="b"),
    ]
    pilot = App(view, size=(200, 60)).pilot()
    pilot.press("tab")
    assert pilot.focused is None  # el manejador se quedó con Tab


def test_handler_returning_none_keeps_default_behavior():
    view = lambda: row(on_key=lambda e: None)[button("A", lambda: None, key="a")]
    pilot = App(view, size=(200, 60)).pilot()
    pilot.press("tab")
    assert pilot.focused == "a"


def test_shortcuts_with_matches():
    saved = Signal(0)

    def on_key(e):
        if e.matches("mod+s"):
            saved.update(lambda n: n + 1)
            return True
        return None

    pilot = App(lambda: box(on_key=on_key), size=(50, 50)).pilot()
    pilot.press("ctrl+s" if not _is_mac() else "meta+s")
    pilot.press("s")
    assert saved() == 1


def test_key_event_fields_and_matches():
    events = []
    pilot = App(lambda: box(on_key=events.append), size=(50, 50)).pilot()
    pilot.press("ctrl+shift+k")
    pilot.press("shift+/")
    pilot.press("a")
    k, slash, a = events
    assert (k.key, k.ctrl, k.shift, k.text) == ("K", True, True, None)
    assert k.matches("ctrl+shift+k") and not k.matches("ctrl+k")
    assert slash.shift and slash.matches("/")  # símbolo: Shift no cuenta
    assert a.text == "a" and a.matches("a")
    with pytest.raises(ValueError, match="tecla"):
        a.matches("ctrl+nope")


def test_tab_is_trapped_inside_capture_barrier():
    view = lambda: box()[
        button("Fondo", lambda: None, key="behind"),
        box(position="absolute", top=0, left=0, right=0, bottom=0, on_click=lambda: None, key="backdrop")[
            box(capture=True, key="dialog")[
                button("Aceptar", lambda: None, key="ok"),
                button("Cancelar", lambda: None, key="cancel"),
            ]
        ],
    ]
    pilot = App(view, size=(300, 200)).pilot()
    seen = []
    for _ in range(3):
        pilot.press("tab")
        seen.append(pilot.focused)
    assert seen == ["ok", "cancel", "ok"]


def test_autofocus_when_node_appears_only_once():
    open_ = Signal(False)
    view = lambda: column()[
        button("Abrir", lambda: open_.set(True), key="open"),
        open_() and button("Campo", lambda: None, key="field", autofocus=True),
    ]
    pilot = App(view, size=(200, 100)).pilot()
    assert pilot.focused is None
    pilot.click("open")
    assert pilot.focused == "field"
    pilot.focus("open")
    pilot.frame()
    assert pilot.focused == "open"  # no vuelve a robar el foco en cada reconstrucción


def test_focus_is_lost_when_node_disappears():
    show = Signal(True)
    view = lambda: column()[show() and button("X", lambda: None, key="x"), box(key="other")]
    pilot = App(view, size=(100, 100)).pilot()
    pilot.focus("x")
    show.set(False)
    pilot.frame()
    assert pilot.focused is None


def _scroll_list():
    return lambda: column()[
        scroll(key="list", height=100)[
            [button(f"{i}", lambda: None, key=f"b{i}", height=40) for i in range(10)]
        ]
    ]


def test_tab_scrolls_focused_node_into_view():
    pilot = App(_scroll_list(), size=(200, 200)).pilot()
    for _ in range(5):
        pilot.press("tab")
    assert pilot.focused == "b4"
    pilot.settle()
    _x, y, _w, h = pilot.rect("b4")
    assert y >= 0 and y + h <= 100


def test_arrow_and_page_keys_scroll_under_pointer():
    view = lambda: column()[scroll(key="list", height=100)[[box(height=50) for _ in range(10)]]]
    pilot = App(view, size=(200, 200)).pilot()
    pilot.move_to(50, 50)
    pilot.press("down")
    pilot.settle()
    assert pilot.scroll_offset("list") == (0, 48)
    pilot.press("end")
    pilot.settle()
    assert pilot.scroll_offset("list") == (0, 400)
    pilot.press("pageup")
    pilot.settle()
    assert pilot.scroll_offset("list")[1] < 400


def test_space_without_focused_button_scrolls():
    view = lambda: column()[scroll(key="list", height=100)[[box(height=50) for _ in range(10)]]]
    pilot = App(view, size=(200, 200)).pilot()
    pilot.move_to(50, 50)
    pilot.press("space")
    pilot.settle()
    assert pilot.scroll_offset("list")[1] > 0


def test_invalid_combo_and_unknown_focus_raise():
    pilot = App(_buttons(), size=(300, 80)).pilot()
    with pytest.raises(ValueError, match="modificador"):
        pilot.press("hyper+a")
    with pytest.raises(LookupError, match="nope"):
        pilot.focus("nope")


def _is_mac():
    import sys

    return sys.platform == "darwin"
