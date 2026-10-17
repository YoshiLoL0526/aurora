"""`@component`: reutiliza lo que no cambió y reconstruye exactamente lo que sí."""

import pytest
from test_render import _png_pixel

from aurora import DAYLIGHT, MIDNIGHT, App, Signal, box, column, component, row, text
from aurora.reactive import Component


def _counting():
    calls = []

    @component
    def item(label: str, on: bool = False):
        calls.append(label)
        return row(key=f"item-{label}", bg="#F00" if on else None)[text(label)]

    return item, calls


def test_reuses_until_its_arguments_change():
    item, calls = _counting()
    selected = Signal("a")
    other = Signal(0)
    view = lambda: column()[[item(x, selected() == x) for x in "abc"], text(f"{other()}")]
    pilot = App(view, size=(200, 100)).pilot()
    assert calls == ["a", "b", "c"]

    other.set(1)  # no lo lee ningún componente
    pilot.frame()
    assert calls == ["a", "b", "c"]

    selected.set("b")  # solo cambian los argumentos de a y b
    pilot.frame()
    assert calls == ["a", "b", "c", "a", "b"]


def test_rebuilds_when_a_signal_it_reads_changes():
    count = Signal(1)
    calls = []

    @component
    def counter():
        calls.append(count())
        return box(key="bar", width=10 * count(), height=4)

    pilot = App(lambda: column()[counter()], size=(200, 100)).pilot()
    count.set(3)
    pilot.frame()
    assert calls == [1, 3]
    assert pilot.rect("bar")[2] == 30


def test_text_lambdas_are_dependencies_too():
    n = Signal(1)

    @component
    def label():
        return row()[text(lambda: "x" * n(), key="t")]

    pilot = App(lambda: column()[label()], size=(400, 100)).pilot()
    before = pilot.rect("t")[2]
    n.set(10)
    pilot.frame()
    assert pilot.rect("t")[2] > before


def test_nested_dependencies_invalidate_the_outer_component():
    width = Signal(10)
    outer_calls = []

    @component
    def inner():
        return box(key="inner", width=width(), height=4)

    @component
    def outer():
        outer_calls.append(1)
        return column(key="outer")[inner()]

    pilot = App(lambda: column()[outer()], size=(200, 100)).pilot()
    width.set(50)
    pilot.frame()
    assert pilot.rect("inner")[2] == 50
    assert len(outer_calls) == 2


def test_handlers_of_reused_components_still_fire():
    clicks = []

    @component
    def clickable(name: str):
        return box(key=name, width=40, height=20, on_click=lambda: clicks.append(name))

    other = Signal(0)
    pilot = App(lambda: row()[clickable("a"), clickable("b"), text(f"{other()}")], size=(200, 60)).pilot()
    other.set(1)
    pilot.frame()
    pilot.click("b")
    pilot.click("a")
    assert clicks == ["b", "a"]


def test_unhashable_arguments_are_not_memoized():
    calls = []

    @component
    def chips(tags: list[str]):
        calls.append(tuple(tags))
        return row()[[text(t) for t in tags]]

    other = Signal(0)
    pilot = App(lambda: column()[chips(["a", "b"]), text(f"{other()}")], size=(200, 60)).pilot()
    other.set(1)
    pilot.frame()
    assert calls == [("a", "b"), ("a", "b")]


def test_entries_not_used_are_forgotten():
    item, _ = _counting()
    n = Signal(5)
    pilot = App(lambda: column()[[item(str(i)) for i in range(n())]], size=(200, 200)).pilot()
    assert isinstance(item, Component)
    assert len(item.cache) == 5
    n.set(2)
    pilot.frame()
    assert len(item.cache) == 2


def test_two_builders_keep_their_own_memoization():
    # Cada ventana (o piloto) es un dueño distinto: reconstruir una no puede
    # olvidar lo que memorizó la otra.
    item, calls = _counting()
    a = Signal(0)
    b = Signal(0)
    pilot_a = App(lambda: column()[item("x"), text(f"{a()}")], size=(200, 100)).pilot()
    pilot_b = App(lambda: column()[item("y"), text(f"{b()}")], size=(200, 100)).pilot()
    assert calls == ["x", "y"]

    a.set(1)
    pilot_a.frame()
    b.set(1)
    pilot_b.frame()
    # Ninguna reconstrucción volvió a llamar a los componentes: siguen frescos.
    assert calls == ["x", "y"]


def test_a_component_shared_by_two_builders_has_an_entry_each():
    item, calls = _counting()
    n = Signal(0)
    pilot_a = App(lambda: column()[item("s"), text(f"a{n()}")], size=(200, 100)).pilot()
    pilot_b = App(lambda: column()[item("s"), text(f"b{n()}")], size=(200, 100)).pilot()
    assert calls == ["s", "s"]  # una construcción por dueño

    n.set(1)
    pilot_a.frame()
    pilot_b.frame()
    assert calls == ["s", "s"]  # cada dueño reutiliza la suya
    assert pilot_a.rect("item-s") == pilot_b.rect("item-s")


def test_must_return_an_element():
    @component
    def broken():
        return "hola"

    with pytest.raises(TypeError, match="broken"):
        App(lambda: column()[broken()]).pilot()


def test_children_keys_follow_their_keyed_parent():
    # Un nodo sin key toma la de su padre: no cambia si el padre se mueve.
    view = lambda: column()[row(key="fila")[text("a"), box(width=5, height=5)]]
    pilot = App(view, size=(200, 60)).pilot()
    assert pilot.rect("fila/0") is not None
    assert pilot.rect("fila/1")[2] == 5


def _ink(pilot, tmp_path, key):
    x, y, w, h = pilot.rect(key)
    path = tmp_path / "frame.png"
    pilot.png(str(path))
    return _png_pixel(path, int(x + w / 2), int(y + h / 2))


def test_theme_change_reserializes_memoized_components(tmp_path):
    theme = Signal(MIDNIGHT)

    @component
    def swatch():
        return box(key="sw", width=40, height=40, bg="$surface")

    pilot = App(lambda: column(padding=10)[swatch()], theme=theme, size=(100, 100)).pilot()
    dark = _ink(pilot, tmp_path, "sw")
    theme.set(DAYLIGHT)
    pilot.frame()
    assert _ink(pilot, tmp_path, "sw") != dark


def test_inherited_text_style_reaches_memoized_components(tmp_path):
    red = Signal(True)

    @component
    def word():
        return text("MMMM", key="w", size=40, weight=900)

    view = lambda: column(padding=10, color="#FF0000" if red() else "#0000FF")[word()]
    pilot = App(view, size=(200, 80)).pilot()
    x, y, w, h = pilot.rect("w")
    probes = [(int(x + w * i / 12), int(y + h * j / 6)) for i in range(1, 12) for j in range(1, 6)]

    def blue_ink():
        path = tmp_path / "w.png"
        pilot.png(str(path))
        return any(b > 180 and r < 80 for r, _, b in (_png_pixel(path, *p) for p in probes))

    assert not blue_ink()
    red.set(False)
    pilot.frame()
    assert blue_ink()


def test_inserting_items_matches_a_fresh_app(tmp_path):
    item, _ = _counting()
    items = Signal(["b", "c", "d"])
    selected = Signal("c")
    view = lambda: column(gap=2)[[item(x, selected() == x) for x in items()]]
    pilot = App(view, size=(200, 200)).pilot()
    for change in (
        lambda: items.set(["a", *items()]),
        lambda: selected.set("a"),
        lambda: items.set(list(reversed(items()))),
        lambda: items.set(["d", "b"]),
    ):
        change()
        pilot.frame()
        fresh = App(view, size=(200, 200)).pilot()
        mine, theirs = tmp_path / "a.png", tmp_path / "b.png"
        pilot.png(str(mine))
        fresh.png(str(theirs))
        assert mine.read_bytes() == theirs.read_bytes()
        for x in items():
            assert pilot.rect(f"item-{x}") == fresh.rect(f"item-{x}")
