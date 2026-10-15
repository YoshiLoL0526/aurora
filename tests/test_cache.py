"""Caché de layout y de párrafos entre frames: se reutiliza solo cuando nada lo invalida."""

from test_render import _png_pixel

from aurora import App, Signal, box, column, row, text, textarea


def test_layout_is_reused_until_something_changes():
    count = Signal(0)
    view = lambda: column()[text(f"n = {count()}", key="t"), box(key="b", width=10 + count() * 10, height=4)]
    pilot = App(view, size=(200, 100)).pilot()
    assert pilot.stats["layout_cached"] is False

    pilot.frame()
    assert pilot.stats["layout_cached"] is True
    pilot.move_to(5, 5)
    assert pilot.stats["layout_cached"] is True

    count.set(2)
    pilot.frame()
    assert pilot.stats["layout_cached"] is False
    assert pilot.rect("b")[2] == 30

    pilot.resize(300, 100)
    assert pilot.stats["layout_cached"] is False
    pilot.frame()
    assert pilot.stats["layout_cached"] is True


def test_editing_without_rebuild_relayouts():
    # La composición del IME no pasa por Python: el layout tiene que notarlo igualmente.
    notes = Signal("")
    view = lambda: column(padding=10)[textarea(notes, key="t", rows=1, width=120)]
    pilot = App(view, size=(300, 300)).pilot()
    pilot.focus("t")
    before = pilot.rect("t")[3]
    pilot.ime_preedit("palabra " * 12)
    assert pilot.stats["rebuilt"] is False
    assert pilot.stats["layout_cached"] is False
    assert pilot.rect("t")[3] > before
    pilot.ime_preedit("")
    assert pilot.rect("t")[3] == before


def test_recycled_paragraphs_keep_their_own_color(tmp_path):
    # El mismo texto con otro color es otro párrafo: no puede reutilizarse el anterior.
    red = Signal(True)
    view = lambda: column(padding=10)[
        text("MMMM", key="t", size=40, weight=900, color="#FF0000" if red() else "#0000FF"),
    ]
    pilot = App(view, size=(200, 80)).pilot()
    x, y, w, h = pilot.rect("t")
    probes = [(int(x + w * i / 12), int(y + h * j / 6)) for i in range(1, 12) for j in range(1, 6)]

    def inks(name):
        path = tmp_path / name
        pilot.png(str(path))
        pixels = [_png_pixel(path, *p) for p in probes]
        return {
            "red": any(r > 180 and b < 80 for r, _, b in pixels),
            "blue": any(b > 180 and r < 80 for r, _, b in pixels),
        }

    assert inks("a.png") == {"red": True, "blue": False}
    red.set(False)
    pilot.frame()
    assert inks("b.png") == {"red": False, "blue": True}


def test_reordered_texts_measure_like_new_ones():
    # Los párrafos se reciclan por contenido: al invertir el orden, cada texto
    # conserva su tamaño y el layout coincide con el de una app recién creada.
    words = Signal(["a", "texto bastante más largo", "medio"])
    view = lambda: row(gap=4)[[text(w, key=f"w{i}") for i, w in enumerate(words())]]
    pilot = App(view, size=(400, 60)).pilot()
    words.set(list(reversed(words())))
    pilot.frame()

    fresh = App(view, size=(400, 60)).pilot()
    for i in range(3):
        assert pilot.rect(f"w{i}") == fresh.rect(f"w{i}")
