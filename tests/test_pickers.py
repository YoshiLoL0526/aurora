"""Componentes de entrada con panel o pasos: number_input, combobox y date_picker."""

from datetime import date

import pytest
from test_render import _png_pixel

from aurora import App, Signal, column, combobox, date_picker, number_input, text
from aurora.components import _state


@pytest.fixture(autouse=True)
def _fresh_state():
    """Cada test empieza con los desplegables cerrados y sin texto a medias."""
    for store in (_state._OPEN, _state._DRAFTS, _state._QUERIES, _state._ACTIVE, _state._MONTHS):
        store.clear()


def _shown(pilot, key):
    """El texto que muestra un campo, tal como lo lee un lector de pantalla."""
    for node in pilot.a11y_tree():
        if node["key"] == key:
            return node.get("value")
    raise AssertionError(f"no hay nodo con key {key!r}")


def _retype(pilot, key, content):
    pilot.click(key)
    pilot.press("mod+a")
    pilot.type(content)


# --- number_input -------------------------------------------------------------


def _number(value, **kwargs):
    view = lambda: column(padding=10, gap=10)[number_input(value, key="n", **kwargs), text("x", key="otro")]
    return App(view, size=(300, 200)).pilot()


def test_number_input_typing_assigns_valid_numbers():
    value = Signal(3)
    pilot = _number(value, min=0, max=10)
    _retype(pilot, "n-field", "7")
    assert value() == 7
    assert isinstance(value(), int)


def test_number_input_waits_while_out_of_range_and_clamps_on_enter():
    value, seen = Signal(3), []
    pilot = _number(value, min=0, max=10, on_change=seen.append)
    _retype(pilot, "n-field", "42")
    assert value() == 4  # el «4» ya era válido; «42» queda fuera del rango y espera
    assert _shown(pilot, "n-field") == "42"
    pilot.press("enter")
    assert value() == 10
    assert _shown(pilot, "n-field") == "10"
    assert seen == [4, 10]


def test_number_input_restores_value_after_unparsable_text():
    value = Signal(3)
    pilot = _number(value)
    _retype(pilot, "n-field", "-")
    assert value() == 3
    pilot.press("enter")
    assert _shown(pilot, "n-field") == "3"


def test_number_input_arrows_and_buttons_step_and_clamp():
    value = Signal(8)
    pilot = _number(value, min=0, max=10, step=2)
    pilot.focus("n-field")
    pilot.press("up")
    assert value() == 10
    pilot.press("up")
    assert value() == 10  # no pasa del máximo
    pilot.click("n-up")  # deshabilitado en el máximo
    assert value() == 10
    pilot.click("n-down")
    pilot.click("n-down")
    assert value() == 6
    assert _shown(pilot, "n-field") == "6"


def test_number_input_floats_round_to_step_decimals_and_accept_comma():
    value = Signal(2.5)
    pilot = _number(value, step=0.25)
    assert _shown(pilot, "n-field") == "2.50"
    _retype(pilot, "n-field", "1,5")
    assert value() == 1.5
    pilot.press("enter")
    assert _shown(pilot, "n-field") == "1.50"
    pilot.press("up")
    assert value() == 1.75


def test_number_input_is_a_spinbutton_for_screen_readers():
    pilot = _number(Signal(3), min=0, max=10)
    roles = {n["key"]: n["role"] for n in pilot.a11y_tree()}
    assert roles["n-field"] == "spinbutton"


def test_number_input_rejects_bad_ranges():
    with pytest.raises(ValueError, match="max"):
        number_input(Signal(1), min=5, max=1)
    with pytest.raises(ValueError, match="step"):
        number_input(Signal(1), step=0)


# --- combobox -------------------------------------------------------------------

CITIES = [("mad", "Madrid"), ("avi", "Ávila"), ("bcn", "Barcelona"), ("sev", "Sevilla")]


def _combo(value, **kwargs):
    view = lambda: column(padding=10)[combobox(value, CITIES, key="c", **kwargs)]
    return App(view, size=(320, 360)).pilot()


def _visible_options(pilot):
    return [i for i in range(len(CITIES)) if pilot.rect(f"c-opt-{i}") is not None]


def test_combobox_filters_ignoring_case_and_accents():
    value = Signal(None)
    pilot = _combo(value)
    pilot.click("c-field")
    pilot.type("AV")
    assert _visible_options(pilot) == [1]  # «Ávila»
    pilot.click("c-opt-1")
    assert value() == "avi"
    assert _visible_options(pilot) == []
    assert _shown(pilot, "c-field") == "Ávila"


def test_combobox_keyboard_highlight_and_enter():
    value, seen = Signal("mad"), []
    pilot = _combo(value, on_change=seen.append)
    pilot.click("c-field")
    pilot.press("mod+a")
    pilot.type("a")  # Madrid, Ávila, Barcelona, Sevilla
    pilot.press("down")
    pilot.press("down")
    pilot.press("enter")
    assert value() == "bcn"
    assert seen == ["bcn"]
    assert _shown(pilot, "c-field") == "Barcelona"


def test_combobox_escape_restores_the_chosen_label():
    value = Signal("sev")
    pilot = _combo(value)
    pilot.click("c-field")
    pilot.press("mod+a")
    pilot.type("zzz")
    assert _visible_options(pilot) == []
    assert pilot.rect("c") is not None
    pilot.press("escape")
    assert value() == "sev"
    assert _shown(pilot, "c-field") == "Sevilla"


def test_combobox_chevron_opens_full_list():
    pilot = _combo(Signal("mad"))
    pilot.click("c-toggle")
    assert _visible_options(pilot) == [0, 1, 2, 3]
    pilot.click("c-toggle")
    assert _visible_options(pilot) == []


# --- date_picker ----------------------------------------------------------------


def _dates(value, **kwargs):
    view = lambda: column(padding=10)[date_picker(value, key="d", **kwargs)]
    return App(view, size=(360, 460)).pilot()


def test_date_picker_opens_on_the_value_month_and_chooses():
    value, seen = Signal(date(2026, 3, 10)), []
    pilot = _dates(value, on_change=seen.append)
    assert pilot.rect("d-day-2026-03-10") is None
    pilot.click("d")
    assert pilot.rect("d-day-2026-03-10") is not None
    pilot.click("d-day-2026-03-21")
    assert value() == date(2026, 3, 21)
    assert seen == [date(2026, 3, 21)]
    assert pilot.rect("d-day-2026-03-21") is None  # se cerró


def test_date_picker_navigates_months_and_respects_limits():
    value = Signal(date(2026, 1, 15))
    pilot = _dates(value, min=date(2026, 1, 10), max=date(2026, 2, 20))
    pilot.click("d")
    pilot.click("d-prev")  # diciembre queda fuera del rango: no navega
    assert pilot.rect("d-day-2026-01-15") is not None
    pilot.click("d-day-2026-01-05")  # antes de `min`: no se elige
    assert value() == date(2026, 1, 15)
    pilot.click("d-next")
    pilot.click("d-day-2026-02-03")
    assert value() == date(2026, 2, 3)


def test_date_picker_keyboard_moves_days_weeks_and_months():
    value = Signal(date(2026, 1, 31))
    pilot = _dates(value)
    pilot.focus("d")
    pilot.press("enter")  # abre
    pilot.press("right")
    assert value() == date(2026, 2, 1)
    assert pilot.rect("d-day-2026-02-01") is not None  # el mes visible sigue al valor
    pilot.press("up")
    assert value() == date(2026, 1, 25)
    pilot.press("pagedown")
    assert value() == date(2026, 2, 25)
    pilot.press("escape")
    assert pilot.rect("d-day-2026-02-25") is None


def test_date_picker_week_starts_on_requested_day():
    pilot = _dates(Signal(date(2026, 10, 19)), first_weekday=6)
    pilot.click("d")
    # Octubre de 2026 empieza en jueves: con semanas de domingo, la primera celda es el 27 de sept.
    first = pilot.rect("d-day-2026-09-27")
    assert first is not None
    assert pilot.rect("d-day-2026-09-26") is None
    assert first[1] < pilot.rect("d-day-2026-10-04")[1]


def test_date_picker_today_button_and_placeholder():
    value = Signal(None)
    pilot = _dates(value)
    pilot.click("d")
    pilot.click("d-today")
    assert value() == date.today()


def test_date_picker_cells_announce_full_dates():
    pilot = _dates(Signal(date(2026, 10, 19)))
    pilot.click("d")
    labels = {n["key"]: n.get("label") for n in pilot.a11y_tree()}
    assert labels["d-day-2026-10-19"] == "lunes, 19 de octubre de 2026"


def test_date_picker_rejects_bad_arguments():
    with pytest.raises(ValueError, match="first_weekday"):
        date_picker(Signal(None), first_weekday=7)
    with pytest.raises(ValueError, match="max"):
        date_picker(Signal(None), min=date(2026, 2, 1), max=date(2026, 1, 1))


# --- render ----------------------------------------------------------------------


def test_pickers_render_selected_day_in_primary(tmp_path):
    _state._OPEN["dr"] = Signal(True)
    day = date(2026, 10, 19)
    view = lambda: column(padding=10)[date_picker(Signal(day), key="dr")]
    app = App(view, size=(360, 460))
    pilot = app.pilot()
    x, y, _, h = pilot.rect(f"dr-day-{day.isoformat()}")
    path = tmp_path / "cal.png"
    app.render_png(str(path), scale=1)
    # El día elegido va relleno del color primario del tema (MIDNIGHT: #7C5CFF).
    r, g, b = _png_pixel(path, int(x + 4), int(y + h / 2))
    assert (r, g, b) == (0x7C, 0x5C, 0xFF)
