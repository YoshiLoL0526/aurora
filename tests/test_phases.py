"""Invalidación por fases: cada cambio rehace solo las fases que le afectan
(estilo → layout → pintura → composición), y lo repintado por zonas es idéntico
a pintar el frame entero."""

from test_render import _png_rows

from aurora import App, Signal, button, column, row, scroll, select, text, text_input, tooltip

SIZE = (480, 360)


def _list_app(n=30):
    selected = Signal(0)
    color = Signal("#E6E8F0")

    def view():
        return column(padding=12, gap=8)[
            text("Lista", key="titulo", size=18),
            scroll(key="lista", height=240, gap=2)[
                [
                    row(
                        key=f"r{i}",
                        padding=(6, 10),
                        radius=6,
                        bg="#2A2F45" if i == selected() else None,
                        bg_hover="#22263A",
                        on_click=lambda i=i: selected.set(i),
                    )[text(f"Fila {i}", key=f"t{i}", color=color() if i == selected() else "#9AA0B8")]
                    for i in range(n)
                ]
            ],
        ]

    return App(view, size=SIZE), selected, color


def _height(damage):
    return damage[3] if damage else 0


def test_idle_frame_paints_nothing():
    app, *_ = _list_app()
    pilot = app.pilot()
    assert pilot.stats["damage"] == (0, 0, *SIZE)
    pilot.settle()
    pilot.frame()
    assert pilot.stats["damage"] is None
    assert pilot.stats["layout_cached"] is True


def test_hover_repaints_only_the_hovered_row():
    app, *_ = _list_app()
    pilot = app.pilot()
    x, y, _, h = pilot.rect("r3")
    pilot.move_to(x + 5, y + 5)
    assert pilot.stats["rebuilt"] is False
    assert pilot.stats["layout_cached"] is True
    damage = pilot.stats["damage"]
    assert damage is not None
    # La fila (y un margen para el antialiasing), no la lista entera.
    assert damage[1] <= y and damage[1] + damage[3] >= y + h
    assert damage[3] < 3 * h


def test_paint_only_rebuild_keeps_layout_and_repaints_what_changed():
    app, selected, color = _list_app()
    pilot = app.pilot()
    pilot.settle()
    selected.set(1)
    pilot.frame()
    assert pilot.stats["rebuilt"] is True
    assert pilot.stats["layout_cached"] is True
    # Las filas 0 y 1, no toda la ventana.
    _, y0, _, _ = pilot.rect("r0")
    _, y1, _, h1 = pilot.rect("r1")
    damage = pilot.stats["damage"]
    assert damage[1] <= y0 and damage[1] + damage[3] >= y1 + h1
    assert _height(damage) < 4 * h1

    # Un texto que solo cambia de color tampoco rehace el layout.
    color.set("#FF0000")
    pilot.frame()
    assert pilot.stats["layout_cached"] is True
    assert _height(pilot.stats["damage"]) <= 3 * h1


def test_layout_change_repaints_the_whole_window():
    width = Signal(100)
    view = lambda: column(padding=10)[row(key="b", width=width(), height=20, bg="#F00")]
    pilot = App(view, size=SIZE).pilot()
    width.set(200)
    pilot.frame()
    assert pilot.stats["layout_cached"] is False
    assert pilot.stats["damage"] == (0, 0, *SIZE)
    assert pilot.rect("b")[2] == 200


def test_scroll_moves_regions_without_relayout():
    app, selected, _ = _list_app()
    pilot = app.pilot()
    before = pilot.rect("r8")
    pilot.scroll("lista", 100)
    assert pilot.stats["rebuilt"] is False
    assert pilot.stats["layout_cached"] is True
    after = pilot.rect("r8")
    assert after[1] == before[1] - 100
    # Solo se repinta la zona visible del `scroll`.
    _, ly, _, lh = pilot.rect("lista")
    damage = pilot.stats["damage"]
    assert damage[1] >= ly - 1 and damage[1] + damage[3] <= ly + lh + 1
    # Las regiones movidas reciben los clics en su sitio nuevo.
    pilot.click_at(after[0] + 5, after[1] + after[3] / 2)
    assert selected() == 8


def test_new_handler_updates_hit_regions():
    clicks = []
    armed = Signal(False)
    view = lambda: column(padding=10)[
        row(key="b", width=80, height=30, bg="#333", on_click=(lambda: clicks.append(1)) if armed() else None)
    ]
    pilot = App(view, size=SIZE).pilot()
    pilot.click("b")
    assert clicks == []
    armed.set(True)
    pilot.frame()
    pilot.click("b")
    assert clicks == [1]


def test_incremental_frames_match_a_full_repaint(tmp_path):
    selected = Signal(0)
    value = Signal("hola")
    choice = Signal("a")
    accent = Signal("#7C5CFF")

    def view():
        return column(padding=12, gap=8)[
            row(gap=8, align="center")[
                button("Uno", lambda: None, key="b1"),
                tooltip(button("Dos", lambda: None, key="b2"), "Un tooltip de ayuda"),
                text_input(value, key="campo", width=120),
                select(choice, [("a", "Alfa"), ("b", "Beta"), ("c", "Gamma")], key="sel", width=110),
            ],
            scroll(key="lista", height=220, gap=2, border_width=1, border_color="#444", radius=8)[
                [
                    row(
                        key=f"r{i}",
                        padding=(6, 10),
                        radius=6,
                        bg="#2A2F45" if i == selected() else None,
                        bg_hover="#22263A",
                        shadow=(0, 2, 8, "#00000080"),
                        on_click=lambda i=i: selected.set(i),
                    )[text(f"Fila {i}", color=accent() if i == selected() else "#9AA0B8")]
                    for i in range(30)
                ]
            ],
        ]

    pilot = App(view, size=SIZE).pilot()
    step = 0

    def check(name):
        nonlocal step
        pilot.settle()
        mine, full = tmp_path / f"{step}-{name}.png", tmp_path / f"{step}-{name}-full.png"
        pilot.png(str(mine))
        # Una superficie nueva no tiene ningún frame: se pinta entera.
        pilot.resize(*SIZE)
        assert pilot.stats["damage"] == (0, 0, *SIZE)
        pilot.png(str(full))
        assert _max_difference(mine, full) <= 2, name
        step += 1

    pilot.move_to(*_center(pilot, "b1"))
    check("hover")
    pilot.move_to(*_center(pilot, "r3"))
    check("hover-fila")
    pilot.click("r3")
    check("seleccion")
    pilot.wheel(130)
    check("scroll")
    pilot.move_to(*_center(pilot, "r12"))
    check("hover-tras-scroll")
    accent.set("#FF5A5A")
    pilot.frame()
    check("color")
    pilot.click("campo")
    pilot.type("!")
    check("escribir")
    pilot.move_to(*_center(pilot, "b2"))
    for _ in range(50):
        pilot.frame()
    check("tooltip")
    pilot.click("sel")
    check("desplegable")
    pilot.press("escape")
    check("cerrado")
    pilot.press("tab")
    check("foco")


def _max_difference(a, b):
    """Mayor diferencia entre dos PNG en un canal. Skia puede redondear distinto el
    antialiasing de una figura que el recorte de la zona dañada corta por la mitad:
    se tolera ±1-2 niveles, invisible y sin acumularse (cada repintado parte de cero)."""
    if a.read_bytes() == b.read_bytes():
        return 0
    (_, rows_a), (_, rows_b) = _png_rows(a), _png_rows(b)
    return max(abs(x - y) for ra, rb in zip(rows_a, rows_b, strict=True) for x, y in zip(ra, rb, strict=True))


def _center(pilot, key):
    x, y, w, h = pilot.rect(key)
    return x + w / 2, y + h / 2
