"""Tests del núcleo nativo usando el render headless."""

import struct
import zlib
from pathlib import Path

import pytest

from aurora import MIDNIGHT, App, _core, box, card, column, row, text


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def _png_rows(path: Path, count: int | None = None) -> tuple[int, list[bytearray]]:
    """Decodificador PNG mínimo (8 bits RGB/RGBA, sin entrelazado) para no depender de Pillow.

    Devuelve los canales por píxel y las primeras `count` filas (todas si es `None`)."""
    data = path.read_bytes()
    pos, idat, width, height, channels = 8, b"", 0, 0, 0
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        chunk = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height = struct.unpack(">II", chunk[:8])
            channels = {2: 3, 6: 4}[chunk[9]]
        elif kind == b"IDAT":
            idat += chunk
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * channels
    prev = bytearray(stride)
    rows = []
    for row_index in range(height if count is None else count):
        start = row_index * (stride + 1)
        ftype, line = raw[start], bytearray(raw[start + 1 : start + 1 + stride])
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b, c = prev[i], prev[i - channels] if i >= channels else 0
            if ftype == 1:
                line[i] = (line[i] + a) & 0xFF
            elif ftype == 2:
                line[i] = (line[i] + b) & 0xFF
            elif ftype == 3:
                line[i] = (line[i] + (a + b) // 2) & 0xFF
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        rows.append(line)
        prev = line
    return channels, rows


def _png_pixel(path: Path, x: int, y: int) -> tuple[int, int, int]:
    channels, rows = _png_rows(path, y + 1)
    r, g, b = rows[y][x * channels : x * channels + 3]
    return r, g, b


def test_render_png_size_respects_scale(tmp_path):
    out = tmp_path / "out.png"
    _core.render_png(box(bg="#112233").to_spec(MIDNIGHT), 200, 100, str(out), 2.0)
    assert _png_size(out) == (400, 200)


def test_background_and_absolute_layout(tmp_path):
    out = tmp_path / "abs.png"
    tree = box(bg="#000000")[box(position="absolute", left=50, top=10, width=20, height=20, bg="#FF0000"),]
    _core.render_png(tree.to_spec(MIDNIGHT), 100, 50, str(out), 1.0)
    assert _png_pixel(out, 5, 5) == (0, 0, 0)
    assert _png_pixel(out, 60, 20) == (255, 0, 0)


def test_percentage_width(tmp_path):
    out = tmp_path / "pct.png"
    tree = row(bg="#000000")[box(width="50%", height="100%", bg="#00FF00")]
    _core.render_png(tree.to_spec(MIDNIGHT), 100, 10, str(out), 1.0)
    assert _png_pixel(out, 45, 5) == (0, 255, 0)
    assert _png_pixel(out, 55, 5) == (0, 0, 0)


def test_percent_inset_positions_absolute_children():
    view = lambda: box(width=200, height=50, padding=(0, 40, 0, 10))[
        box(key="pct", position="absolute", left="50%", top=10, width=10, height=10)
    ]
    pilot = App(view, size=(220, 60)).pilot()
    # El porcentaje se resuelve contra la caja de relleno del padre (200): 10 + 100.
    assert pilot.rect("pct") == (110, 10, 10, 10)


def test_overflow_hidden_clips_painting(tmp_path):
    out = tmp_path / "clip.png"
    tree = box(bg="#000000")[
        # El hijo no se encoge: desborda y el recorte es lo que lo oculta.
        box(width=40, height=20, overflow="hidden", bg="#111111")[
            box(width=40, height=60, shrink=0, bg="#00FF00")
        ]
    ]
    _core.render_png(tree.to_spec(MIDNIGHT), 60, 40, str(out), 1.0)
    assert _png_pixel(out, 20, 10) == (0, 255, 0)
    assert _png_pixel(out, 20, 30) == (0, 0, 0)


def test_full_app_renders(tmp_path):
    out = tmp_path / "app.png"

    def view():
        return column(padding=24, gap=12)[
            card()[text("Hola", size=24, weight=700), text("texto largo " * 20, max_lines=2)],
        ]

    App(view, size=(400, 300)).render_png(str(out), scale=1.0)
    assert _png_size(out) == (400, 300)


@pytest.mark.parametrize("bad", ["#12", "rojo", "#GGGGGG"])
def test_invalid_color_raises(tmp_path, bad):
    with pytest.raises(ValueError, match="color"):
        _core.render_png(box(bg=bad).to_spec(MIDNIGHT), 10, 10, str(tmp_path / "x.png"), 1.0)


@pytest.mark.parametrize("bad", ["#é1", "#ñññ", "#€€"])
def test_non_ascii_color_raises_value_error_not_panic(tmp_path, bad):
    with pytest.raises(ValueError, match="color"):
        _core.render_png(box(bg=bad).to_spec(MIDNIGHT), 10, 10, str(tmp_path / "x.png"), 1.0)


def test_duplicate_keys_are_rejected(tmp_path):
    tree = row()[box(key="ok", on_click=lambda: None), box(key="ok", on_click=lambda: None)]
    with pytest.raises(ValueError, match="key duplicada"):
        _core.render_png(tree.to_spec(MIDNIGHT), 10, 10, str(tmp_path / "x.png"), 1.0)


def test_explicit_key_colliding_with_positional_key_is_rejected(tmp_path):
    # Los nodos sin key reciben su ruta en el árbol ("0/1", ...) como identidad.
    tree = row()[box(key="0/1"), box()]
    with pytest.raises(ValueError, match="key duplicada"):
        _core.render_png(tree.to_spec(MIDNIGHT), 10, 10, str(tmp_path / "x.png"), 1.0)


def test_unique_keys_render(tmp_path):
    tree = row()[box(key="a"), box(key="b"), box()]
    _core.render_png(tree.to_spec(MIDNIGHT), 10, 10, str(tmp_path / "x.png"), 1.0)


def test_inspector_outlines_the_selected_node(tmp_path):
    def view():
        return column(key="root", padding=40)[box(key="target", width=120, height=60, bg="#202020")]

    pilot = App(view, size=(900, 400)).pilot(inspector=True)
    pilot.press("f12")
    pilot.click("aurora:inspector-tree#1")
    pilot.settle()
    x, y, w, h = pilot.rect("target")
    out = tmp_path / "inspector.png"
    pilot.png(str(out))
    # Contorno rosa del nodo elegido y, por encima, la etiqueta oscura.
    r, g, b = _png_pixel(out, int(x + w / 2), int(y))
    assert r > 200 and g < 140 and b > 120
    r, g, b = _png_pixel(out, int(x + w / 2), int(y + h / 2))
    assert (r, g, b) == (0x20, 0x20, 0x20)
    label = _png_pixel(out, int(x + 4), int(y - 6))
    assert max(label) < 0x40
