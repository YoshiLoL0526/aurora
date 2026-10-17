"""Animaciones declarativas: transiciones de estilo, de layout, de entrada y de salida."""

import pytest
from test_phases import _checker, _matches
from test_render import _png_rows

from aurora import App, Signal, animate, box, column, row, scroll, text

BG = (0x0B, 0x0D, 0x14)
RED = (0xFF, 0x00, 0x00)
BLUE = (0x00, 0x00, 0xFF)
LINEAR = animate.tween(1.0, easing="linear")


def _pixel(pilot, tmp_path, x, y):
    path = tmp_path / "frame.png"
    pilot.png(str(path))
    channels, rows = _png_rows(path, y + 1)
    return tuple(rows[y][x * channels : x * channels + 3])


def _near(a, b, tol=6):
    return all(abs(p - q) <= tol for p, q in zip(a, b, strict=True))


def _mix(a, b, t):
    return tuple(round(p + (q - p) * t) for p, q in zip(a, b, strict=True))


def _brightest(path, y):
    """Color más intenso de la fila: el trazo de un glifo, libre de antialiasing."""
    channels, rows = _png_rows(path, y + 1)
    row = rows[y]
    return max(
        (tuple(row[x * channels : x * channels + 3]) for x in range(len(row) // channels)),
        key=sum,
    )


# --- API ------------------------------------------------------------------------


def test_curves_validate_their_parameters():
    with pytest.raises(ValueError, match="positivos"):
        animate.spring(stiffness=0)
    with pytest.raises(ValueError, match="negativa"):
        animate.tween(-1)
    with pytest.raises(ValueError, match="easing"):
        animate.tween(0.2, easing="bounce")  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="delay"):
        animate.spring(delay=-0.1)
    with pytest.raises(ValueError, match="escala"):
        animate.zoom(-1)


def test_presets_describe_their_effect():
    assert animate.fade() == animate.Effect(opacity=0.0)
    assert animate.slide(y=8) == animate.Effect(opacity=0.0, y=8.0)
    assert animate.zoom(0.9, fade=False) == animate.Effect(scale=0.9)


def test_invalid_values_raise_clear_errors():
    for props, message in [
        ({"transition": 0.3}, "transition debe ser"),
        ({"enter": "fade"}, "enter debe ser un efecto"),
        ({"animate_layout": "sí"}, "transition debe ser"),
    ]:
        app = App(lambda props=props: box(width=10, height=10, **props), size=(40, 40))
        with pytest.raises(ValueError, match=message):
            app.pilot()


# --- Transiciones de estilo -----------------------------------------------------------


def test_style_changes_animate_from_the_shown_value(tmp_path):
    color = Signal("#FF0000")
    app = App(lambda: column()[box(bg=color(), width=40, height=40, transition=LINEAR)], size=(60, 60))
    pilot = app.pilot()
    assert _pixel(pilot, tmp_path, 20, 20) == RED
    color.set("#0000FF")
    pilot.frame(0.5)
    assert _near(_pixel(pilot, tmp_path, 20, 20), _mix(RED, BLUE, 0.5))
    # Cambiar de destino a medias sigue desde lo que se ve, sin saltos.
    color.set("#FF0000")
    pilot.frame(0.0)
    assert _near(_pixel(pilot, tmp_path, 20, 20), _mix(RED, BLUE, 0.5))
    pilot.settle()
    assert _pixel(pilot, tmp_path, 20, 20) == RED


def test_without_transition_changes_are_immediate(tmp_path):
    color = Signal("#FF0000")
    app = App(lambda: column()[box(bg=color(), width=40, height=40)], size=(60, 60))
    pilot = app.pilot()
    color.set("#0000FF")
    pilot.frame()
    assert _pixel(pilot, tmp_path, 20, 20) == BLUE


def test_text_color_transitions(tmp_path):
    color = Signal("#FF0000")

    def view():
        return column(bg="#000000", padding=10)[text("█", size=40, color=color(), transition=LINEAR, key="t")]

    pilot = App(view, size=(120, 90)).pilot()
    _x, y, _w, h = pilot.rect("t")
    axis = int(y + h / 2)
    out = tmp_path / "text.png"
    pilot.png(str(out))
    assert _brightest(out, axis) == RED

    color.set("#0000FF")
    pilot.frame()  # el primer frame pinta el color anterior
    pilot.frame(0.5)
    pilot.png(str(out))
    assert _near(_brightest(out, axis), _mix(RED, BLUE, 0.5), tol=12)
    pilot.settle()
    pilot.png(str(out))
    assert _brightest(out, axis) == BLUE


def test_inherited_text_color_changes_instantly(tmp_path):
    """El `transition` de un contenedor no anima el color que heredan sus textos:
    el texto necesita su propia transición (limitación conocida)."""
    color = Signal("#FF0000")

    def view():
        return column(bg="#000000", color=color(), transition=LINEAR)[text("█", size=40, key="t")]

    pilot = App(view, size=(120, 90)).pilot()
    _x, y, _w, h = pilot.rect("t")
    axis = int(y + h / 2)
    color.set("#0000FF")
    pilot.frame()
    pilot.frame(0.5)
    out = tmp_path / "inherited.png"
    pilot.png(str(out))
    # Sin transición propia, el texto ya está en el color nuevo.
    assert _brightest(out, axis) == BLUE


def test_opacity_transition_and_appearing_background(tmp_path):
    visible = Signal(False)
    app = App(
        lambda: column()[box(bg="#FF0000" if visible() else None, width=40, height=40, transition=LINEAR)],
        size=(60, 60),
    )
    pilot = app.pilot()
    assert _pixel(pilot, tmp_path, 20, 20) == BG
    visible.set(True)
    pilot.frame(0.5)
    assert _near(_pixel(pilot, tmp_path, 20, 20), _mix(BG, RED, 0.5), tol=8)
    pilot.settle()
    assert _pixel(pilot, tmp_path, 20, 20) == RED


# --- Layout -----------------------------------------------------------------------


def _layout_app():
    tall = Signal(False)

    def view():
        return column()[
            box(key="hueco", height=60 if tall() else 0),
            box(key="item", bg="#FF0000", width=40, height=20, animate_layout=LINEAR),
        ]

    return App(view, size=(60, 120)), tall


def test_layout_changes_slide_to_the_new_box(tmp_path):
    app, tall = _layout_app()
    pilot = app.pilot()
    tall.set(True)
    pilot.frame()
    # El layout (y el hit-testing) ya es el nuevo; lo pintado sale de la caja anterior.
    assert pilot.rect("item") == (0, 60, 40, 20)
    assert _pixel(pilot, tmp_path, 20, 10) == RED
    pilot.frame(0.5)
    assert _pixel(pilot, tmp_path, 20, 10) == BG
    assert _pixel(pilot, tmp_path, 20, 35) == RED
    pilot.settle()
    assert _pixel(pilot, tmp_path, 20, 35) == BG
    assert _pixel(pilot, tmp_path, 20, 70) == RED


def test_resizing_the_window_does_not_animate_the_layout(tmp_path):
    view = lambda: row(justify="end")[box(key="item", bg="#FF0000", width=20, height=20, animate_layout=True)]
    pilot = App(view, size=(100, 40)).pilot()
    pilot.resize(60, 40)
    assert pilot.frame() is False
    assert _pixel(pilot, tmp_path, 50, 10) == RED


# --- Entrada y salida ---------------------------------------------------------------


def _presence_app(**props):
    shown = Signal(True)

    def view():
        return column()[
            shown() and box(key="caja", bg="#FF0000", width=40, height=40, **props),
            box(key="pie", bg="#0000FF", width=40, height=20),
        ]

    return App(view, size=(60, 80)), shown


def test_enter_does_not_play_on_the_first_frame(tmp_path):
    app, _ = _presence_app(enter=animate.fade(transition=LINEAR))
    pilot = app.pilot()
    assert _pixel(pilot, tmp_path, 20, 20) == RED
    assert pilot.frame() is False


def test_appearing_nodes_play_their_enter_effect(tmp_path):
    app, shown = _presence_app(enter=animate.fade(transition=LINEAR))
    shown.set(False)
    pilot = app.pilot()
    shown.set(True)
    pilot.frame()
    assert _pixel(pilot, tmp_path, 20, 20) == BG
    pilot.frame(0.5)
    assert _near(_pixel(pilot, tmp_path, 20, 20), _mix(BG, RED, 0.5), tol=8)
    pilot.settle()
    assert _pixel(pilot, tmp_path, 20, 20) == RED


def test_enter_effects_move_and_scale(tmp_path):
    app, shown = _presence_app(enter=animate.slide(x=40, fade=False, transition=LINEAR))
    shown.set(False)
    pilot = app.pilot()
    shown.set(True)
    pilot.frame(0.5)
    # A mitad de camino está desplazada 20 px a la derecha.
    assert _pixel(pilot, tmp_path, 10, 20) == BG
    assert _pixel(pilot, tmp_path, 50, 20) == RED


def test_removed_nodes_play_their_exit_effect(tmp_path):
    app, shown = _presence_app(exit=animate.fade(transition=LINEAR))
    pilot = app.pilot()
    shown.set(False)
    pilot.frame(0.5)
    # Ya no está en la vista (ni recibe eventos): el pie sube a su sitio y la
    # instantánea del que sale se pinta encima, a medio desvanecer.
    assert pilot.rect("caja") is None
    assert pilot.rect("pie") == (0, 0, 40, 20)
    assert _near(_pixel(pilot, tmp_path, 20, 30), _mix(BG, RED, 0.5), tol=8)
    assert pilot.frame() is True
    pilot.settle()
    assert _pixel(pilot, tmp_path, 20, 30) == BG
    assert _pixel(pilot, tmp_path, 20, 10) == BLUE


def test_a_node_that_comes_back_while_leaving_enters_from_where_it_was(tmp_path):
    app, shown = _presence_app(enter=animate.fade(), exit=animate.fade(), transition=LINEAR)
    pilot = app.pilot()
    shown.set(False)
    pilot.frame(0.5)
    shown.set(True)
    pilot.frame(0.0)
    assert _near(_pixel(pilot, tmp_path, 20, 20), _mix(BG, RED, 0.5), tol=8)
    pilot.settle()
    assert _pixel(pilot, tmp_path, 20, 20) == RED


def test_settle_waits_for_the_exit():
    app, shown = _presence_app(exit=animate.zoom(transition=animate.tween(0.2)))
    pilot = app.pilot()
    shown.set(False)
    pilot.frame()
    assert pilot.frame() is True
    pilot.settle()
    assert pilot.frame() is False


def test_render_png_shows_the_final_state(tmp_path):
    view = lambda: column()[box(bg="#FF0000", width=40, height=40, enter=animate.fade(), animate_layout=True)]
    path = tmp_path / "x.png"
    App(view, size=(60, 60)).render_png(str(path), scale=1)
    channels, rows = _png_rows(path, 21)
    assert tuple(rows[20][20 * channels : 20 * channels + 3]) == RED


# --- Repintado por zonas -------------------------------------------------------------


def test_animated_frames_leave_no_trace(tmp_path):
    items = Signal(list(range(6)))

    def view():
        return column(padding=12, gap=6)[
            text("Tareas", key="titulo"),
            [
                row(
                    key=f"t{i}",
                    padding=8,
                    radius=6,
                    bg="#2A2F45",
                    shadow=(0, 2, 6, "#00000066"),
                    animate_layout=True,
                    enter=animate.slide(y=-10),
                    exit=animate.zoom(0.8),
                )[text(f"Tarea {i}", key=f"l{i}")]
                for i in items()
            ],
        ]

    pilot = App(view, size=(480, 360)).pilot()
    check = _checker(pilot, tmp_path)
    check("inicio")
    items.set([0, 1, 3, 4, 5])
    check("quita")
    items.set([7, 0, 1, 3, 4, 5])
    check("añade")
    items.set([5, 4, 3, 1, 0, 7])
    check("invierte")
    # Varios cambios seguidos, sin dejar que terminen las animaciones.
    for order in ([4, 3, 1], [1, 3, 9, 4], [9, 1]):
        items.set(order)
        pilot.frame()
        pilot.frame()
    check("seguidos")


def _twin(tmp_path, make, changes, size, steps=8):
    """Cada frame de la animación, pintado por zonas, es idéntico al de un piloto
    gemelo que lo pinta entero (una superficie nueva por frame)."""
    mine, state_a = make()
    full, state_b = make()
    for n, change in enumerate(changes):
        for step in range(steps):
            # La marca de `wake()` es global: cada piloto reconstruye justo después
            # de su cambio, o el primero la consumiría por los dos.
            if step == 0:
                change(*state_a)
            mine.frame()
            if step == 0:
                change(*state_b)
            full.resize(*size)
            a, b = tmp_path / f"{n}-{step}.png", tmp_path / f"{n}-{step}-full.png"
            mine.png(str(a))
            full.png(str(b))
            assert _matches(a, b), (n, step)


def _task(i, bg="#2A2F45"):
    return row(
        key=f"t{i}",
        padding=8,
        radius=6,
        bg=bg,
        shadow=(0, 2, 6, "#00000066"),
        transition=animate.spring(stiffness=200, damping=18),
        animate_layout=True,
        enter=animate.slide(x=-30),
        exit=animate.zoom(0.7),
    )[text(f"Tarea {i}", key=f"l{i}")]


def test_frames_mid_animation_match_a_full_repaint(tmp_path):
    size = (320, 260)

    def make():
        items, bg = Signal([0, 1, 2, 3]), Signal("#2A2F45")
        view = lambda: column(padding=12, gap=6)[[_task(i, bg() if i == 1 else "#2A2F45") for i in items()]]
        return App(view, size=size).pilot(), (items, bg)

    changes = [
        lambda items, bg: items.set([0, 2, 3]),
        lambda items, bg: items.set([3, 5, 0, 2]),
        lambda items, bg: (items.set([3, 1, 5, 0, 2]), bg.set("#7C5CFF")),
    ]
    _twin(tmp_path, make, changes, size)


def test_scroll_and_overlay_animations_match_a_full_repaint(tmp_path):
    size = (320, 260)

    def make():
        items, modal = Signal(list(range(10))), Signal(False)

        def view():
            return column(padding=12)[
                scroll(key="lista", height=200, gap=6)[[_task(i) for i in items()]],
                modal()
                and box(
                    key="modal",
                    layer="overlay",
                    position="absolute",
                    top=40,
                    left=40,
                    width=200,
                    height=120,
                    radius=12,
                    bg="#7C5CFF",
                    shadow=(0, 8, 24, "#000000AA"),
                    enter=animate.zoom(0.9),
                    exit=animate.slide(y=20),
                )[text("Modal", key="modal-texto")],
            ]

        pilot = App(view, size=size).pilot()
        pilot.scroll("lista", 60)
        pilot.settle()
        return pilot, (items, modal)

    changes = [
        lambda items, modal: items.set([0, 1, 2, 4, 5, 6, 7, 8, 9]),
        lambda items, modal: modal.set(True),
        lambda items, modal: (modal.set(False), items.set([9, 0, 1, 2, 4, 5])),
    ]
    _twin(tmp_path, make, changes, size, steps=10)
