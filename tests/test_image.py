"""Imágenes: tamaño natural y proporción, fit, recorte, SVG, bytes, caché y errores."""

import os
from pathlib import Path

import pytest
from test_render import _png_pixel

from aurora import MIDNIGHT, App, Signal, _core, box, column, image, row

RED, BLUE, GREEN, BLACK = (255, 0, 0), (0, 0, 255), (0, 128, 0), (0, 0, 0)


@pytest.fixture
def split_png(tmp_path) -> Path:
    """PNG de 40×20: mitad izquierda roja, mitad derecha azul."""
    path = tmp_path / "split.png"
    tree = row()[box(width=20, height=20, bg="#FF0000"), box(width=20, height=20, bg="#0000FF")]
    _core.render_png(tree.to_spec(MIDNIGHT), 40, 20, str(path), 1.0)
    return path


def _render(tmp_path, tree, size=(100, 100)):
    out = tmp_path / "out.png"
    _core.render_png(tree.to_spec(MIDNIGHT), *size, str(out), 1.0)
    return lambda x, y: _png_pixel(out, x, y)


def test_natural_size_without_stretching(split_png):
    pilot = App(lambda: column()[image(split_png, key="img")], size=(200, 100)).pilot()
    assert pilot.rect("img") == (0, 0, 40, 20)


def test_one_side_derives_the_other_from_aspect_ratio(split_png):
    view = lambda: column()[image(split_png, key="w", width=80), image(split_png, key="h", height=10)]
    pilot = App(view, size=(200, 100)).pilot()
    assert pilot.rect("w")[2:] == (80, 40)
    assert pilot.rect("h")[2:] == (20, 10)


def test_shrinks_to_available_width(split_png):
    pilot = App(lambda: column()[row(width=30)[image(split_png, key="img")]], size=(200, 100)).pilot()
    assert pilot.rect("img")[2:] == (30, 15)


def test_fit_contain(tmp_path, split_png):
    px = _render(tmp_path, box(bg="#000000")[image(split_png, width=100, height=100, fit="contain")])
    assert px(10, 50) == RED and px(90, 50) == BLUE
    assert px(50, 10) == BLACK  # márgenes arriba y abajo


def test_fit_cover(tmp_path, split_png):
    px = _render(tmp_path, box(bg="#000000")[image(split_png, width=100, height=100, fit="cover")])
    assert px(25, 50) == RED and px(75, 50) == BLUE
    assert px(50, 3) != BLACK  # sin márgenes: se recorta a los lados


def test_fit_fill(tmp_path, split_png):
    px = _render(tmp_path, box(bg="#000000")[image(split_png, width=100, height=100, fit="fill")])
    assert px(25, 95) == RED and px(75, 5) == BLUE


def test_radius_clips_the_image(tmp_path, split_png):
    tree = box(bg="#000000")[image(split_png, width=100, height=100, fit="cover", radius=50)]
    px = _render(tmp_path, tree)
    assert px(2, 2) == BLACK
    assert px(25, 50) == RED


def test_bytes_source(tmp_path, split_png):
    data = split_png.read_bytes()
    px = _render(tmp_path, box(bg="#000000")[image(data, width=100, height=100, fit="fill")])
    assert px(25, 50) == RED


def test_svg_with_size_and_with_only_viewbox(tmp_path):
    sized = tmp_path / "sized.svg"
    sized.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30">'
        '<rect width="30" height="30" fill="green"/></svg>'
    )
    boxed = tmp_path / "viewbox.svg"
    boxed.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 20"/>')
    view = lambda: column(bg="#000000")[image(sized, key="a"), image(boxed, key="b")]
    pilot = App(view, size=(100, 100)).pilot()
    assert pilot.rect("a")[2:] == (30, 30)
    assert pilot.rect("b")[2:] == (10, 20)
    out = tmp_path / "svg.png"
    pilot.png(str(out))
    assert _png_pixel(out, 15, 15) == GREEN


def test_svg_scales_crisply(tmp_path):
    icon = tmp_path / "icon.svg"
    icon.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        '<rect width="5" height="10" fill="red"/></svg>'
    )
    px = _render(tmp_path, box(bg="#000000")[image(icon, width=100, height=100)])
    assert px(40, 50) == RED and px(60, 50) == BLACK


def test_changed_file_is_reloaded(tmp_path):
    path = tmp_path / "live.png"
    _core.render_png(box(bg="#FF0000").to_spec(MIDNIGHT), 10, 10, str(path), 1.0)
    tick = Signal(0)
    view = lambda: box(bg="#000000", key=f"r{tick()}")[image(path, width=50, height=50, fit="fill")]
    pilot = App(view, size=(50, 50)).pilot()
    out = tmp_path / "live-out.png"
    pilot.png(str(out))
    assert _png_pixel(out, 25, 25) == RED
    _core.render_png(box(bg="#0000FF").to_spec(MIDNIGHT), 30, 30, str(path), 1.0)
    # La caché va por ruta + mtime + tamaño, y en NTFS dos escrituras seguidas
    # pueden compartir marca de tiempo: se adelanta el mtime para que el cambio
    # sea inequívoco (el tamaño también cambia: 10×10 → 30×30).
    later = path.stat().st_mtime + 1
    os.utime(path, (later, later))
    tick.set(1)
    pilot.frame()
    pilot.png(str(out))
    assert _png_pixel(out, 25, 25) == BLUE


def test_missing_file_raises_file_not_found(tmp_path):
    missing = tmp_path / "nope.png"
    with pytest.raises(FileNotFoundError, match=r"nope\.png"):
        App(lambda: image(missing), size=(50, 50)).pilot()


def test_corrupt_file_raises_value_error(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"esto no es una imagen")
    with pytest.raises(ValueError, match="decodificar"):
        _core.render_png(image(bad).to_spec(MIDNIGHT), 10, 10, str(tmp_path / "x.png"), 1.0)


def test_invalid_fit_raises(tmp_path, split_png):
    with pytest.raises(ValueError, match="fit"):
        bad = image(split_png, fit="zoom")  # ty: ignore[invalid-argument-type]
        _core.render_png(bad.to_spec(MIDNIGHT), 10, 10, str(tmp_path / "x.png"), 1.0)
