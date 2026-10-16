"""`aurora build`: configuración, argumentos de PyInstaller, `resource()` y un empaquetado real."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_render import _png_rows, _png_size

from aurora import resource
from aurora.build import BuildError, destination, pyinstaller_args, resolve
from aurora.cli import main


def project(tmp_path: Path, settings: str = "", script: str = "main.py") -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "demo"\n\n[tool.aurora.build]\n{settings}\n', encoding="utf-8"
    )
    (tmp_path / script).write_text("print('hola')\n", encoding="utf-8")
    return tmp_path


def test_defaults_from_main_py(tmp_path):
    config = resolve(cwd=project(tmp_path))
    assert config.script == tmp_path.resolve() / "main.py"
    assert config.name == "main"
    assert config.dist == tmp_path.resolve() / "dist"
    assert config.onefile and not config.console
    args = pyinstaller_args(config)
    assert "--windowed" in args
    assert ("--onedir" if sys.platform == "darwin" else "--onefile") in args
    assert args[args.index("--workpath") + 1] == str(tmp_path.resolve() / "build")


def test_pyproject_settings(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(b"")
    (tmp_path / "data.json").write_text("{}")
    settings = """
script = "app.py"
name = "Mi App"
include = ["assets", "data.json"]
onefile = false
console = true
"""
    config = resolve(cwd=project(tmp_path, settings, script="app.py"))
    assert config.name == "Mi App"
    assert not config.onefile and config.console
    args = pyinstaller_args(config)
    assert "--onedir" in args and "--console" in args
    data = [args[i + 1] for i, a in enumerate(args) if a == "--add-data"]
    root = tmp_path.resolve()
    assert data == [f"{root / 'assets'}{os.pathsep}assets", f"{root / 'data.json'}{os.pathsep}."]


def test_options_override_pyproject_and_include_adds(tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.txt").write_text("")
    config = resolve(
        name="Otro", include=["b.txt"], onefile=False, console=True, dist="out",
        cwd=project(tmp_path, 'name = "Mi App"\ninclude = ["a.txt"]'),
    )  # fmt: skip
    assert config.name == "Otro"
    assert [p.name for p in config.include] == ["a.txt", "b.txt"]
    assert config.dist == tmp_path.resolve() / "out"
    assert not config.onefile and config.console


def test_settings_paths_are_relative_to_pyproject(tmp_path):
    root = project(tmp_path, 'script = "main.py"')
    sub = root / "src"
    sub.mkdir()
    config = resolve(cwd=sub)  # lanzado desde una subcarpeta del proyecto
    assert config.script == root.resolve() / "main.py"
    assert config.dist == root.resolve() / "dist"


def test_executable_and_output_paths(tmp_path):
    config = resolve(cwd=project(tmp_path), console=True)
    exe = "main.exe" if sys.platform == "win32" else "main"
    assert config.executable == config.dist / exe == config.output
    config.onefile = False
    assert config.executable == config.dist / "main" / exe
    assert config.output == config.dist / "main"


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ('scritp = "main.py"', "clave desconocida"),
        ("onefile = 1", "onefile debe ser bool"),
        ('include = "assets"', "include debe ser list"),
        ('include = ["falta"]', "no existe"),
        ('script = "falta.py"', "no existe"),
        ('icon = "falta.ico"', "no existe"),
        ('name = "a/b"', "nombre de ejecutable inválido"),
    ],
)
def test_invalid_settings(tmp_path, settings, message):
    with pytest.raises(BuildError, match=message):
        resolve(cwd=project(tmp_path, settings))


def test_missing_script_explains_what_to_do(tmp_path):
    with pytest.raises(BuildError, match=r"aurora build app\.py"):
        resolve(cwd=tmp_path)


def test_invalid_toml(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.aurora.build\n")
    with pytest.raises(BuildError, match="no es TOML válido"):
        resolve(cwd=tmp_path)


def test_destination_keeps_structure_relative_to_script(tmp_path):
    script = tmp_path / "app" / "main.py"
    (tmp_path / "app" / "assets" / "icons").mkdir(parents=True)
    (tmp_path / "app" / "assets" / "icons" / "x.svg").write_text("")
    (tmp_path / "fuera.txt").write_text("")
    assert destination(tmp_path / "app" / "assets", script) == "assets"
    assert destination(tmp_path / "app" / "assets" / "icons" / "x.svg", script) == "assets/icons"
    assert destination(tmp_path / "fuera.txt", script) == "."


def test_cli_reports_errors_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    assert "aurora build: error: no encuentro el script" in capsys.readouterr().err


def test_resource_resolves_from_main_script_or_bundle(tmp_path, monkeypatch):
    main_module = sys.modules["__main__"]
    monkeypatch.setattr(main_module, "__file__", str(tmp_path / "app.py"), raising=False)
    assert resource("assets/logo.png") == str(tmp_path.resolve() / "assets" / "logo.png")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    assert resource("assets/logo.png") == str(tmp_path / "bundle" / "assets" / "logo.png")
    absolute = str(tmp_path / "x.png")
    assert resource(absolute) == absolute


APP = """
import sys
from pathlib import Path
from aurora import App, column, image, resource, text

note = Path(resource("assets/nota.txt")).read_text(encoding="utf-8")
dot = image(resource("assets/punto.svg"), width=40, height=40)
app = App(lambda: column()[text(note), dot], size=(120, 80))
app.render_png(sys.argv[1], scale=1)
"""

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    '<rect width="10" height="10" fill="#FF0000"/></svg>'
)


@pytest.mark.skipif(
    not os.environ.get("AURORA_BUILD_TEST") or importlib.util.find_spec("PyInstaller") is None,
    reason="empaquetado real (~30 s): AURORA_BUILD_TEST=1 y PyInstaller instalado",
)
def test_packaged_app_runs_from_another_folder(tmp_path):
    (tmp_path / "proj").mkdir()
    root = project(tmp_path / "proj", 'include = ["assets"]')
    (root / "main.py").write_text(APP, encoding="utf-8")
    (root / "assets").mkdir()
    (root / "assets" / "nota.txt").write_text("hola", encoding="utf-8")
    (root / "assets" / "punto.svg").write_text(SVG, encoding="utf-8")

    cli = [sys.executable, "-m", "aurora", "build", "--console"]
    subprocess.run(cli, cwd=root, check=True, timeout=600)
    config = resolve(cwd=root, console=True)
    assert config.executable.is_file()

    # Desde otra carpeta: los recursos se encuentran por `resource()`, no por el directorio actual.
    out = tmp_path / "shot.png"
    elsewhere = tmp_path / "otra"
    elsewhere.mkdir()
    subprocess.run([str(config.executable), str(out)], cwd=elsewhere, check=True, timeout=120)
    assert _png_size(out) == (120, 80)
    channels, rows = _png_rows(out)
    red = bytes((255, 0, 0))
    assert any(row[i : i + 3] == red for row in rows for i in range(0, len(row), channels))
