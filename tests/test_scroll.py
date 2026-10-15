"""Contenedor `scroll`: layout, desplazamiento, recorte, encadenado y barra."""

import pytest
from test_render import _png_pixel

from aurora import MIDNIGHT, App, Signal, _core, box, column, row, scroll


def _list_view(count=10, *, clicks=None, **scroll_style):
    def item(i):
        on_click = (lambda: clicks.append(i)) if clicks is not None else None
        return box(key=f"i{i}", height=50, on_click=on_click)

    return lambda: column()[scroll(key="list", height=100, **scroll_style)[[item(i) for i in range(count)]]]


def test_children_keep_their_size_and_content_overflows():
    pilot = App(_list_view(), size=(100, 200)).pilot()
    assert pilot.rect("list")[3] == 100
    assert pilot.rect("i0")[3] == 50  # no se encogen para caber
    assert pilot.rect("i9")[1] == 450
    assert pilot.scroll_offset("list") == (0, 0)


def test_wheel_scrolls_and_moves_children():
    pilot = App(_list_view(), size=(100, 200)).pilot()
    pilot.scroll("list", dy=120)
    assert pilot.scroll_offset("list") == (0, 120)
    assert pilot.rect("i0")[1] == -120


def test_offset_is_clamped_to_content():
    pilot = App(_list_view(), size=(100, 200)).pilot()
    pilot.scroll("list", dy=10_000)
    assert pilot.scroll_offset("list") == (0, 400)
    pilot.scroll("list", dy=-10_000)
    assert pilot.scroll_offset("list") == (0, 0)


def test_padding_is_part_of_the_scrollable_content():
    pilot = App(_list_view(padding=10), size=(100, 200)).pilot()
    pilot.scroll("list", dy=10_000)
    assert pilot.scroll_offset("list") == (0, 420)


def test_mouse_wheel_lines_are_smooth():
    pilot = App(_list_view(), size=(100, 200)).pilot()
    pilot.move_to(50, 50)
    pilot.wheel(1, lines=True)
    assert 0 < pilot.scroll_offset("list")[1] < 48
    pilot.settle()
    assert pilot.scroll_offset("list") == (0, 48)


def test_clipped_children_do_not_receive_clicks():
    clicks = []
    pilot = App(_list_view(clicks=clicks), size=(100, 200)).pilot()
    pilot.click("i5")  # está debajo del área visible: el clic no le llega
    assert clicks == []
    pilot.scroll("list", dy=250)
    pilot.click("i5")
    assert clicks == [5]


def test_offset_survives_rebuilds_and_clamps_when_content_shrinks():
    count = Signal(10)
    view = lambda: column()[
        box(key="less", height=20, on_click=lambda: count.set(3)),
        scroll(key="list", height=100)[[box(key=f"i{i}", height=50) for i in range(count())]],
    ]
    pilot = App(view, size=(100, 200)).pilot()
    pilot.scroll("list", dy=200)
    pilot.frame()
    assert pilot.scroll_offset("list") == (0, 200)
    pilot.click("less")
    assert pilot.scroll_offset("list") == (0, 50)


def test_nested_scroll_chains_to_outer_at_the_limit():
    view = lambda: scroll(key="outer")[
        scroll(key="inner", height=100, grow=0)[[box(height=50) for _ in range(4)]],
        box(height=300),
    ]
    pilot = App(view, size=(100, 200)).pilot()
    pilot.scroll("inner", dy=100)
    assert pilot.scroll_offset("inner") == (0, 100)
    assert pilot.scroll_offset("outer") == (0, 0)
    pilot.wheel(dy=50)  # el interior ya está al final: se desplaza el exterior
    assert pilot.scroll_offset("outer") == (0, 50)


def test_horizontal_scroll_accepts_vertical_wheel():
    view = lambda: column()[scroll(key="strip", axis="x", height=40)[[box(width=50) for _ in range(5)]]]
    pilot = App(view, size=(100, 100)).pilot()
    pilot.scroll("strip", dy=30)
    assert pilot.scroll_offset("strip") == (30, 0)


def test_dragging_the_scrollbar_thumb():
    pilot = App(_list_view(), size=(100, 200)).pilot()
    pilot.move_to(96, 5)  # franja de la barra, sobre el pulgar
    pilot.mouse_down()
    pilot.move_to(96, 500)
    assert pilot.scroll_offset("list") == (0, 400)
    pilot.mouse_up()
    pilot.move_to(96, 50)
    assert pilot.scroll_offset("list") == (0, 400)  # sin botón ya no arrastra


def test_pressing_the_track_does_not_click_content():
    clicks = []
    pilot = App(_list_view(clicks=clicks), size=(100, 200)).pilot()
    pilot.click_at(96, 80)
    assert clicks == []
    assert pilot.scroll_offset("list")[1] > 0  # salta hacia donde se pulsó


def test_scrollbar_shows_on_hover_and_hides_after(tmp_path):
    view = lambda: column(bg="#000000")[
        scroll(key="list", height=100, scrollbar_color="#FF0000")[[box(height=50) for _ in range(10)]]
    ]
    pilot = App(view, size=(100, 200)).pilot()
    out = tmp_path / "bar.png"
    pilot.png(str(out))
    assert _png_pixel(out, 95, 10) == (0, 0, 0)  # oculta en reposo

    pilot.move_to(96, 50)
    pilot.settle()
    pilot.png(str(out))
    r, g, b = _png_pixel(out, 95, 10)
    assert r > 100 and g == 0 and b == 0

    pilot.move_to(20, 150)
    pilot.settle()
    pilot.png(str(out))
    assert _png_pixel(out, 95, 10) == (0, 0, 0)


def test_content_is_clipped(tmp_path):
    out = tmp_path / "clip.png"
    tree = column(bg="#000000")[scroll(height=50)[box(height=200, bg="#00FF00")]]
    _core.render_png(tree.to_spec(MIDNIGHT), 100, 100, str(out), 1.0)
    assert _png_pixel(out, 10, 40) == (0, 255, 0)
    assert _png_pixel(out, 10, 60) == (0, 0, 0)


def test_overlay_inside_scroll_escapes_the_clip(tmp_path):
    view = lambda: column(bg="#000000")[
        scroll(height=50)[
            row(height=200)[
                box(layer="overlay", position="absolute", top=40, width=20, height=40, bg="#FF0000")
            ]
        ]
    ]
    out = tmp_path / "overlay.png"
    _core.render_png(App(view)._build(), 100, 100, str(out), 1.0)
    assert _png_pixel(out, 10, 70) == (255, 0, 0)


def test_invalid_scroll_axis_raises(tmp_path):
    with pytest.raises(ValueError, match="scroll"):
        _core.render_png(box(scroll="z").to_spec(MIDNIGHT), 10, 10, str(tmp_path / "x.png"), 1.0)
