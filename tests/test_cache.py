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


def _states():
    """Vistas que reordenan, mueven entre padres, añaden, quitan y cambian de tipo nodos con key."""
    long = "un texto bastante largo que tiene que partirse en varias líneas"
    return [
        lambda: column(gap=4)[
            row(key="a", gap=4)[text("uno", key="t1"), box(key="b1", width=20, height=20, bg="#F00")],
            row(key="b")[text("dos", key="t2")],
        ],
        # Hijos de `a` invertidos, `b` primero y un texto que cambia.
        lambda: column(gap=4)[
            row(key="b")[text("dos dos dos", key="t2")],
            row(key="a", gap=4)[box(key="b1", width=40, height=10, bg="#0F0"), text("uno", key="t1")],
        ],
        # `t1` cambia de padre, `b1` desaparece y aparece `c`.
        lambda: column(gap=4)[
            row(key="b")[text("dos", key="t2"), text("uno", key="t1")], box(key="c", height=30)
        ],
        # `t1` pasa de texto a contenedor (con hijos).
        lambda: column(gap=4)[row(key="a")[box(key="t1", padding=4, bg="#00F")[text("x", key="tx")]]],
        # Mismo texto en un ancho distinto: hay que volver a partir las líneas.
        lambda: column()[box(key="w", width=120)[text(long, key="t1")]],
        lambda: column()[box(key="w", width=260)[text(long, key="t1")]],
        # Solo cambia la pintura.
        lambda: column()[box(key="w", width=260, bg="#333")[text(long, key="t1", color="#FF0")]],
    ]


def test_reconciled_layout_matches_a_fresh_one(tmp_path):
    states = _states()
    current = Signal(0)
    view = lambda: states[current()]()
    pilot = App(view, size=(320, 200)).pilot()
    # 4 → 5 → 4: el ancho vuelve a uno ya medido (la medición memorizada acierta).
    order = [*range(len(states)), 3, 0, 5, 4, 2, 1, 4, 5, 4]
    for step, i in enumerate(order):
        current.set(i)
        pilot.frame()
        fresh = App(states[i], size=(320, 200)).pilot()
        for key in ("a", "b", "c", "t1", "t2", "b1", "tx", "w"):
            assert pilot.rect(key) == fresh.rect(key), (i, key)
        # Mismos píxeles: el párrafo reutilizado está maquetado con el ancho correcto.
        mine, theirs = tmp_path / f"{step}-a.png", tmp_path / f"{step}-b.png"
        pilot.png(str(mine))
        fresh.png(str(theirs))
        assert mine.read_bytes() == theirs.read_bytes(), i


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
