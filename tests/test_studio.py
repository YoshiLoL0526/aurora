"""La demo `examples/studio.py` ejercitada con el piloto: un test de humo de punta a punta."""

import runpy
from pathlib import Path

import pytest

STUDIO = Path(__file__).parent.parent / "examples" / "studio.py"


@pytest.fixture
def studio():
    # Cada test carga el módulo de nuevo: el estado (Signals) empieza limpio.
    return runpy.run_path(str(STUDIO), run_name="studio")


def test_new_task_with_shortcut_form_and_enter(studio):
    pilot = studio["app"].pilot(size=(1280, 820))
    before = len(studio["tasks"]())
    pilot.press("mod+n")
    assert pilot.focused == "new-title"  # autofocus al abrir el formulario
    pilot.type("Escribir la guía de la v0.2")
    pilot.press("enter")
    tasks = studio["tasks"]()
    assert len(tasks) == before + 1
    assert tasks[-1].title == "Escribir la guía de la v0.2"
    assert studio["modal"]() is None


def test_escape_closes_the_form_without_creating(studio):
    pilot = studio["app"].pilot(size=(1280, 820))
    before = len(studio["tasks"]())
    pilot.click("add")
    pilot.type("A medias")
    pilot.press("escape")
    assert studio["modal"]() is None
    assert len(studio["tasks"]()) == before


def test_board_search_filters_tasks(studio):
    pilot = studio["app"].pilot(size=(1280, 820))
    pilot.click("nav-tablero")
    pilot.click("search")
    pilot.type("vault")
    visible = [t for t in studio["tasks"]() if pilot.rect(f"task-{t.id}") is not None]
    assert [t.title for t in visible] == ["Rebalanceo semanal del vault"]


def test_settings_switch_changes_theme(studio):
    pilot = studio["app"].pilot(size=(1280, 820))
    pilot.click("nav-ajustes")
    assert studio["theme"]() is studio["MIDNIGHT"]
    pilot.click("set-dark")
    assert studio["theme"]() is studio["DAYLIGHT"]
    pilot.click("set-tabs-notificaciones")
    pilot.click("set-mentions")
    assert studio["notify_mentions"]() is True


def test_gallery_renders(studio, tmp_path):
    studio["render_gallery"](tmp_path)
    assert len(list(tmp_path.glob("*.png"))) == 6
