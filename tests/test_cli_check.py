"""`aurora shot`, `tree`, `check` y `pilot`: comprobar una app sin ventana desde la terminal.

Las apps de prueba están en `tests/apps/`. Cada comando ejecuta el script desde cero, como
`python script.py`, pero `App.run()` no abre ventana.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aurora import _script, _tree
from aurora._headless import ScriptError, UsageError, load, pick_window, start
from aurora.cli import main

APPS = Path(__file__).resolve().parent / "apps"
CONTADOR = str(APPS / "contador.py")
AVISOS = str(APPS / "avisos.py")


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


# --- shot ------------------------------------------------------------------------------------------


def test_shot_escribe_un_png(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "c.png"
    code, stdout, _ = run(capsys, "shot", CONTADOR, "-o", str(out))
    assert code == 0
    assert stdout.strip() == str(out)
    assert png_size(out) == (400, 300)


def test_shot_con_escala_tamano_y_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "c.png"
    assert run(capsys, "shot", CONTADOR, "-o", str(out), "--size", "500x200", "--scale", "2")[0] == 0
    assert png_size(out) == (1000, 400)
    code, stdout, _ = run(capsys, "shot", CONTADOR, "-o", str(out), "--key", "add", "--json")
    assert code == 0
    data = json.loads(stdout)
    assert data["ok"] and data["key"] == "add" and Path(data["path"]) == out.resolve()
    w, h = png_size(out)
    assert 60 <= w <= 100 and 30 <= h <= 50  # la caja del botón


def test_shot_key_inexistente_sugiere(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "shot", CONTADOR, "-o", str(tmp_path / "x.png"), "--key", "ad")
    assert code == 1
    assert "'add'" in err
    assert not (tmp_path / "x.png").exists()


def test_shot_tema(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    light, dark = tmp_path / "l.png", tmp_path / "d.png"
    assert run(capsys, "shot", CONTADOR, "-o", str(light), "--theme", "light")[0] == 0
    assert run(capsys, "shot", CONTADOR, "-o", str(dark), "--theme", "dark")[0] == 0
    assert light.read_bytes() != dark.read_bytes()


# --- tree ------------------------------------------------------------------------------------------


def test_tree_muestra_keys_textos_y_cajas(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "tree", CONTADOR)
    assert code == 0
    assert 'button "Sumar" #add @24,63' in out
    assert 'text "Clics: 0" #total' in out
    assert 'textbox placeholder="Tu nombre" #name' in out
    # El texto de un botón no se repite en su propia línea.
    assert out.count('"Sumar"') == 1
    assert "Sin avisos de layout." in out


def test_tree_avisos(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "tree", AVISOS)
    assert code == 0  # los avisos no hacen fallar a `tree`
    assert "text-overflow #desborda" in out and "#estrecha" in out
    assert "text-clipped #cortado" in out
    assert "text-overflow #bajo" in out
    assert "no-label #icono" in out
    assert "offscreen #lejos" in out
    assert "#bien" not in out.split("avisos de layout:")[1]


def test_tree_json_depth_y_key(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "tree", CONTADOR, "--json")
    assert code == 0
    data = json.loads(out)
    keys = [c["key"] for c in data["tree"]["children"]]
    assert "total" in keys and "name" in keys
    add = next(c for c in data["tree"]["children"][1]["children"] if c["key"] == "add")
    assert add["role"] == "button" and add["interactive"] and add["explicit_key"]
    assert data["warnings"] == []

    code, out, _ = run(capsys, "tree", CONTADOR, "--depth", "0")
    assert out.splitlines()[0].startswith("box #0")
    assert "nodos más" in out and "#add" not in out

    code, out, _ = run(capsys, "tree", CONTADOR, "--key", "add")
    assert out.startswith('button "Sumar" #add')
    assert "#total" not in out

    code, _, err = run(capsys, "tree", CONTADOR, "--key", "totl")
    assert code == 1 and "'total'" in err


def test_tree_ventanas(capsys: pytest.CaptureFixture[str]) -> None:
    script = str(APPS / "ventanas.py")
    assert "#main-title" in run(capsys, "tree", script)[1]
    assert "#settings-title" in run(capsys, "tree", script, "--window", "ajustes")[1]
    assert "#settings-title" in run(capsys, "tree", script, "--window", "1")[1]
    code, _, err = run(capsys, "tree", script, "--window", "7")
    assert code == 2
    assert "0 ('Principal'), 1 ('Ajustes')" in err


# --- check -----------------------------------------------------------------------------------------


def test_check_bien(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "check", CONTADOR)
    assert code == 0
    assert out.startswith(f"{CONTADOR}: ok")


def test_check_prop_inventada(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(capsys, "check", str(APPS / "prop_mala.py"))
    assert code == 1
    assert out == ""
    assert "prop_mala.py:7: TypeError: text() no acepta la prop 'colr'. ¿Quisiste decir 'color'?" in err
    assert 'saludo = text("hola", colr="red")' in err
    assert "Traceback" not in err and "elements.py" not in err


def test_check_token_desconocido_apunta_a_la_linea_del_usuario(capsys: pytest.CaptureFixture[str]) -> None:
    # El token falla al serializar (dentro de Aurora); el error señala dónde se creó el elemento.
    code, out, _ = run(capsys, "check", str(APPS / "token_malo.py"), "--json")
    assert code == 1
    error = json.loads(out)["error"]
    assert error["type"] == "ThemeTokenError"
    assert error["file"].endswith("token_malo.py")
    assert error["line"] == 8
    assert error["code"] == 'return column(padding=16, bg="$bg")[titulo]'
    assert "¿Quisiste decir '$background'?" in error["message"]


def test_check_excepcion_en_la_vista(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "check", str(APPS / "vista_rota.py"))
    assert code == 1
    assert "vista_rota.py:7: ZeroDivisionError: division by zero" in err
    assert "return sum(items) / len(items)" in err

    code, _, err = run(capsys, "check", str(APPS / "vista_rota.py"), "--traceback")
    assert code == 1 and "Traceback (most recent call last)" in err

    code, out, _ = run(capsys, "check", str(APPS / "vista_rota.py"), "--json")
    assert code == 1
    error = json.loads(out)["error"]
    assert error["type"] == "ZeroDivisionError" and error["line"] == 7


def test_check_strict_y_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "check", AVISOS)
    assert code == 0 and "5 avisos de layout" in out
    code, out, _ = run(capsys, "check", AVISOS, "--strict", "--json")
    assert code == 1
    data = json.loads(out)
    assert not data["ok"]
    assert {w["code"] for w in data["warnings"]} == {"text-overflow", "text-clipped", "no-label", "offscreen"}


def test_check_errores_de_uso(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "check", str(tmp_path / "no_existe.py"))
    assert code == 2 and "no existe el script" in err

    sin_app = tmp_path / "sin_app.py"
    sin_app.write_text("x = 1\n", encoding="utf-8")
    code, _, err = run(capsys, "check", str(sin_app))
    assert code == 2 and "no crea ninguna App" in err

    sintaxis = tmp_path / "sintaxis.py"
    sintaxis.write_text("from aurora import App\nx = (\n", encoding="utf-8")
    code, _, err = run(capsys, "check", str(sintaxis))
    assert code == 1 and "sintaxis.py:2: SyntaxError" in err

    with pytest.raises(SystemExit) as e:
        main(["check", CONTADOR, "--size", "grande"])
    assert e.value.code == 2


def test_check_tema_propio(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    script = tmp_path / "tema.py"
    script.write_text(
        "from aurora import App, MIDNIGHT, Theme, text\n"
        "App(lambda: text('a'), theme=Theme(colors=dict(MIDNIGHT.colors))).run()\n",
        encoding="utf-8",
    )
    code, _, err = run(capsys, "check", str(script), "--theme", "light")
    assert code == 2 and "tema propio" in err
    assert run(capsys, "check", str(script))[0] == 0


def test_lo_que_imprime_el_script_va_a_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    script = tmp_path / "habla.py"
    script.write_text("from aurora import App, text\nprint('hola')\nApp(lambda: text('a')).run()\n")
    code, out, err = run(capsys, "check", str(script), "--json")
    assert code == 0
    assert json.loads(out)["ok"]
    assert "hola" in err


# --- pilot -----------------------------------------------------------------------------------------


def test_pilot_guion_que_cambia_estado(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    shot = tmp_path / "s.png"
    steps = f"click add; click add; expect text 'Clics: 2'; click name; type Ana; shot {shot}; tree greeting"
    code, out, err = run(capsys, "pilot", CONTADOR, steps)
    assert code == 0, err
    assert "[1] click add" in out
    assert "[7] tree greeting" in out
    assert 'text "Hola, Ana" #greeting' in out
    assert out.rstrip().endswith("ok: 7 pasos")
    assert png_size(shot) == (400, 300)


def test_pilot_key_inexistente(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(capsys, "pilot", CONTADOR, "click add\nclick reste\nclick add")
    assert code == 1
    assert "[1] click add" in out and "[3]" not in out
    assert "falló el paso 2 (click reste)" in err
    assert "¿Quisiste decir 'reset'" in err


def test_pilot_expect_que_falla(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "pilot", CONTADOR, "click add; expect text 'Clics: 5'")
    assert code == 1
    assert "falló el paso 2" in err and "Clics: 1" in err


def test_pilot_json_un_resultado_por_paso(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    steps = "focus name; type hola; expect focused name; tree"
    code, out, _ = run(capsys, "pilot", CONTADOR, "--json", steps)
    assert code == 0
    data = json.loads(out)
    assert data["ok"]
    assert [s["command"] for s in data["steps"]] == ["focus name", "type hola", "expect focused name", "tree"]
    assert all(s["ok"] for s in data["steps"])
    assert data["steps"][3]["tree"]["key"] == "0"

    code, out, _ = run(capsys, "pilot", CONTADOR, "--json", "click add; click nope")
    data = json.loads(out)
    assert code == 1 and not data["ok"]
    assert data["steps"][1]["ok"] is False and "nope" in data["steps"][1]["error"]


def test_pilot_guion_en_archivo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    script = tmp_path / "pasos.txt"
    script.write_text("# sube a 3\nclick add\nclick add; click add\nexpect value total 'Clics: 3'\n")
    code, out, err = run(capsys, "pilot", CONTADOR, "--script", str(script))
    assert code == 0, err
    assert "ok: 4 pasos" in out


def test_pilot_errores_de_sintaxis(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "pilot", CONTADOR, "click add; clik reset")
    assert code == 2
    assert "paso 2" in err and "¿Quisiste decir 'click'?" in err
    code, _, err = run(capsys, "pilot", CONTADOR, "move 10")
    assert code == 2 and "uso: move X Y" in err
    code, _, err = run(capsys, "pilot", CONTADOR, "wait pronto")
    assert code == 2 and "SEGUNDOS debe ser un número" in err
    code, _, err = run(capsys, "pilot", CONTADOR)
    assert code == 2


def test_pilot_excepcion_en_un_manejador(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    script = tmp_path / "falla.py"
    script.write_text(
        "from aurora import App, button\n\n"
        "def guardar():\n"
        "    raise ValueError('sin disco')\n\n"
        "App(lambda: button('Guardar', guardar, key='save')).run()\n",
        encoding="utf-8",
    )
    code, _, err = run(capsys, "pilot", str(script), "click save")
    assert code == 1
    assert "falla.py:4: ValueError: sin disco" in err


# --- La lógica, sin el CLI -------------------------------------------------------------------------


def test_parse_del_guion() -> None:
    steps = _script.parse("click add; type 'hola; mundo'\n# comentario\n\nresize 800x600")
    assert [(s.number, s.name, s.args, s.line) for s in steps] == [
        (1, "click", ["add"], 1),
        (2, "type", ["hola; mundo"], 1),
        (3, "resize", ["800x600"], 4),
    ]
    with pytest.raises(_script.ScriptSyntaxError, match="expect text"):
        _script.parse("expect text a b c")


def test_snapshot_y_avisos_reutilizables() -> None:
    app = load(AVISOS)
    window = pick_window(app, None)
    snap = _tree.snapshot(start(window, size=window.size), window.size)
    assert snap.find("bien") is not None
    assert snap.suggest("bein") == ["bien"]
    codes = sorted((w.code, w.key) for w in snap.warnings())
    assert ("offscreen", "lejos") in codes and ("no-label", "icono") in codes


def test_load_errores() -> None:
    with pytest.raises(UsageError):
        load(APPS / "no_existe.py")
    app = load(APPS / "prop_mala.py")  # la vista no se construye hasta el primer frame
    with pytest.raises(ScriptError) as e:
        start(pick_window(app, None))
    assert e.value.location is not None and e.value.location.line == 7
