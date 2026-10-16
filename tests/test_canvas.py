"""`canvas`: dibujo inmediato desde Python, grabado en lote en el núcleo."""

from array import array

import pytest
from test_render import _png_pixel

from aurora import MIDNIGHT, App, Canvas, Path, Signal, box, canvas, column, component


def _render(tmp_path, draw, size=(100, 100), **style):
    out = tmp_path / "out.png"
    view = lambda: box(bg="#000000")[canvas(draw, grow=1, **style)]
    App(view, size=size).render_png(str(out), scale=1)
    return out


def test_figures_are_painted_at_their_coordinates(tmp_path):
    def draw(c: Canvas):
        c.rect(0, 0, 50, 50, fill="#FF0000")
        c.circle(75, 25, 20, fill="#00FF00")
        c.line(0, 75, 100, 75, stroke="#0000FF", stroke_width=6)
        c.polygon([(50, 85), (100, 85), (100, 100), (50, 100)], fill="#FFFFFF")

    out = _render(tmp_path, draw)
    assert _png_pixel(out, 25, 25) == (255, 0, 0)
    assert _png_pixel(out, 75, 25) == (0, 255, 0)
    assert _png_pixel(out, 50, 75) == (0, 0, 255)
    assert _png_pixel(out, 90, 95) == (255, 255, 255)
    assert _png_pixel(out, 25, 95) == (0, 0, 0)


def test_size_is_known_when_drawing(tmp_path):
    seen = []

    def draw(c: Canvas):
        seen.append((c.width, c.height))
        c.rect(c.width - 10, c.height - 10, 10, 10, fill="#FF0000")

    out = _render(tmp_path, draw, size=(120, 80), padding=10)
    # El origen es la caja de contenido: dentro del padding.
    assert seen == [(100, 60)]
    assert _png_pixel(out, 105, 65) == (255, 0, 0)
    assert _png_pixel(out, 115, 75) == (0, 0, 0)


def test_drawing_is_clipped_to_the_content_box(tmp_path):
    out = _render(tmp_path, lambda c: c.clear("#FF0000"), size=(100, 100), padding=20)
    assert _png_pixel(out, 50, 50) == (255, 0, 0)
    assert _png_pixel(out, 10, 10) == (0, 0, 0)


def test_theme_tokens_and_stroke(tmp_path):
    def draw(c: Canvas):
        c.rect(10, 10, 80, 80, fill="$primary", stroke="#FFFFFF", stroke_width=4)

    out = _render(tmp_path, draw)
    primary = MIDNIGHT.colors["primary"]
    assert _png_pixel(out, 50, 50) == tuple(int(primary[i : i + 2], 16) for i in (1, 3, 5))
    assert _png_pixel(out, 10, 50) == (255, 255, 255)


def test_transforms_and_save_restore(tmp_path):
    def draw(c: Canvas):
        with c.saved():
            c.translate(50, 50)
            c.scale(2)
            c.rect(0, 0, 10, 10, fill="#FF0000")
        c.rect(0, 0, 10, 10, fill="#00FF00")

    out = _render(tmp_path, draw)
    assert _png_pixel(out, 65, 65) == (255, 0, 0)
    assert _png_pixel(out, 5, 5) == (0, 255, 0)


def test_clip_rect(tmp_path):
    def draw(c: Canvas):
        c.clip_rect(0, 0, 50, 100)
        c.clear("#FF0000")

    out = _render(tmp_path, draw)
    assert _png_pixel(out, 25, 50) == (255, 0, 0)
    assert _png_pixel(out, 75, 50) == (0, 0, 0)


def test_path_and_arc(tmp_path):
    def draw(c: Canvas):
        c.path(Path().move_to(0, 0).line_to(50, 0).line_to(50, 50).close(), fill="#FF0000")
        c.arc(75, 75, 20, 0, 360, pie=True, fill="#00FF00")

    out = _render(tmp_path, draw)
    assert _png_pixel(out, 40, 10) == (255, 0, 0)
    assert _png_pixel(out, 10, 40) == (0, 0, 0)
    assert _png_pixel(out, 75, 75) == (0, 255, 0)


def test_points_from_a_buffer_object(tmp_path):
    class Points:
        """Imita a un array de numpy: se convierte con `astype` sin iterarlo."""

        def astype(self, dtype):
            assert dtype == "=f4"
            return array("f", [0, 50, 100, 50])

    out = _render(tmp_path, lambda c: c.polyline(Points(), stroke="#FF0000", stroke_width=10))
    assert _png_pixel(out, 50, 50) == (255, 0, 0)


def test_text_is_drawn(tmp_path):
    def draw(c: Canvas):
        c.text(50, 50, "█", color="#FFFFFF", size=40, align="center", baseline="middle")

    out = _render(tmp_path, draw)
    assert _png_pixel(out, 50, 50) == (255, 255, 255)


def test_invalid_command_raises(tmp_path):
    with pytest.raises(ValueError, match="color"):
        _render(tmp_path, lambda c: c.rect(0, 0, 10, 10, fill="rojo"))
    with pytest.raises(ValueError, match="dash"):
        _render(tmp_path, lambda c: c.line(0, 0, 10, 10, dash=(1,)))


def test_draw_must_be_callable():
    with pytest.raises(TypeError):
        canvas("no")  # ty: ignore[invalid-argument-type]


def test_default_height():
    pilot = App(lambda: column()[canvas(lambda c: None, key="c")], size=(300, 400)).pilot()
    assert pilot.rect("c") == (0, 0, 300, 200)


# --- cuándo se vuelve a llamar a draw ----------------------------------------


def test_redraws_on_resize_but_not_on_idle_frames():
    calls = []
    pilot = App(lambda: column()[canvas(lambda c: calls.append(c.width), grow=1)], size=(200, 100)).pilot()
    assert calls == [200]
    pilot.frame()
    pilot.move_to(10, 10)
    assert calls == [200]
    pilot.resize(300, 100)
    assert calls == [200, 300]


def test_redraws_when_the_view_rebuilds():
    n = Signal(0)
    calls = []

    def view():
        value = n()
        return column()[canvas(lambda c: calls.append(value), grow=1)]

    pilot = App(view, size=(200, 100)).pilot()
    n.set(1)
    pilot.frame()
    assert calls == [0, 1]


def test_memoized_canvas_redraws_only_when_its_signals_change():
    level = Signal(0.5)
    other = Signal(0)
    calls = []

    def draw(c: Canvas):
        calls.append(level())
        c.rect(0, 0, c.width * level(), c.height, fill="#FF0000")

    @component
    def gauge():
        return canvas(draw, key="gauge", height=20)

    def view():
        other()
        return column()[gauge()]

    pilot = App(view, size=(200, 100)).pilot()
    assert calls == [0.5]
    other.set(1)  # reconstruye la vista, pero no lo que dibuja el canvas
    pilot.frame()
    assert pilot.stats["rebuilt"]
    assert calls == [0.5]
    level.set(1.0)  # leído solo dentro de draw: basta para redibujar
    pilot.frame()
    assert calls == [0.5, 1.0]
    # Solo se repinta el lienzo (con 1 px de margen para el antialiasing).
    assert pilot.stats["damage"] == (0, 0, 200, 21)


def test_redraw_repaints_the_canvas(tmp_path):
    color = Signal("#FF0000")
    pilot = App(lambda: box(bg="#000000")[canvas(lambda c: c.clear(color()), grow=1)], size=(50, 50)).pilot()
    out = tmp_path / "a.png"
    pilot.png(str(out))
    assert _png_pixel(out, 25, 25) == (255, 0, 0)
    color.set("#00FF00")
    pilot.frame()
    pilot.png(str(out))
    assert _png_pixel(out, 25, 25) == (0, 255, 0)


def test_canvas_receives_clicks():
    clicks = []
    view = lambda: column()[canvas(lambda c: None, key="c", height=50, on_click=lambda: clicks.append(1))]
    pilot = App(view, size=(100, 100)).pilot()
    pilot.click("c")
    assert clicks == [1]


def test_error_in_draw_surfaces_and_is_not_retried_every_frame():
    calls = []

    def draw(c: Canvas):
        calls.append(1)
        raise RuntimeError("fallo al dibujar")

    with pytest.raises(RuntimeError, match="fallo al dibujar"):
        App(lambda: canvas(draw), size=(100, 100)).pilot()
    assert calls == [1]
