"""Empaquetado de una app en un ejecutable distribuible: lo que hay detrás de `aurora build`.

Aurora no reinventa el empaquetador: prepara la llamada a PyInstaller (núcleo nativo, recursos,
icono, sin consola) a partir de la configuración de `[tool.aurora.build]` en `pyproject.toml` y
de las opciones de la línea de comandos, que tienen prioridad. PyInstaller es una dependencia
opcional (`aurora-ui[build]`): solo hace falta para empaquetar, no para ejecutar la app.

    [tool.aurora.build]
    script = "app.py"            # por defecto: main.py o app.py
    name = "Mi App"              # por defecto: el nombre del script
    icon = "assets/icon.ico"     # .ico en Windows, .icns en macOS (otros formatos, con Pillow)
    include = ["assets"]         # archivos o carpetas que se copian junto a la app
    onefile = true               # un solo archivo; false = carpeta (arranca más rápido)
    console = false              # true = mantener la consola (útil para ver errores)
    upx = false                  # true = comprimir los binarios con UPX (si está instalado)
    dist = "dist"                # carpeta de salida
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomllib

_KEYS = {"script", "name", "icon", "include", "onefile", "console", "upx", "dist"}
_DEFAULT_SCRIPTS = ("main.py", "app.py")
# Formatos de icono que PyInstaller usa tal cual; el resto lo convierte con Pillow.
_NATIVE_ICON = {"win32": ".ico", "darwin": ".icns"}
_INSTALL_HINT = 'instálalo con `uv add --dev "aurora-ui[build]"` o `pip install "aurora-ui[build]"`'


class BuildError(Exception):
    """Configuración o entorno inválidos para empaquetar; el mensaje explica cómo arreglarlo."""


@dataclass
class BuildConfig:
    """Todo lo que hace falta para empaquetar, con rutas absolutas ya validadas."""

    script: Path
    name: str
    root: Path
    dist: Path
    icon: Path | None = None
    include: list[Path] = field(default_factory=list)
    onefile: bool = True
    console: bool = False
    upx: bool = False
    clean: bool = False

    @property
    def app_bundle(self) -> bool:
        """En macOS una app sin consola se empaqueta como `.app` (siempre en modo carpeta)."""
        return sys.platform == "darwin" and not self.console

    @property
    def executable(self) -> Path:
        """Ruta del ejecutable que se genera."""
        exe = self.name + (".exe" if sys.platform == "win32" else "")
        if self.app_bundle:
            return self.dist / f"{self.name}.app" / "Contents" / "MacOS" / self.name
        return self.dist / exe if self.onefile else self.dist / self.name / exe

    @property
    def output(self) -> Path:
        """Lo que se distribuye: el ejecutable, su carpeta o el `.app`."""
        if self.app_bundle:
            return self.dist / f"{self.name}.app"
        return self.executable if self.onefile else self.dist / self.name


def find_project(start: Path) -> Path | None:
    """Carpeta del `pyproject.toml` más cercano subiendo desde `start`, si existe."""
    for folder in (start, *start.parents):
        if (folder / "pyproject.toml").is_file():
            return folder
    return None


def load_settings(project: Path | None) -> dict[str, Any]:
    """Lee `[tool.aurora.build]` del `pyproject.toml` de `project` (vacío si no hay)."""
    if project is None:
        return {}
    path = project / "pyproject.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise BuildError(f"{path} no es TOML válido: {e}") from None
    settings = data.get("tool", {}).get("aurora", {}).get("build", {})
    if not isinstance(settings, dict):
        raise BuildError(f"[tool.aurora.build] en {path} debe ser una tabla")
    unknown = sorted(set(settings) - _KEYS)
    if unknown:
        raise BuildError(
            f"clave desconocida en [tool.aurora.build]: {', '.join(unknown)} "
            f"(válidas: {', '.join(sorted(_KEYS))})"
        )
    return settings


def resolve(
    script: str | None = None,
    *,
    name: str | None = None,
    icon: str | None = None,
    include: list[str] | None = None,
    onefile: bool | None = None,
    console: bool | None = None,
    upx: bool | None = None,
    dist: str | None = None,
    clean: bool = False,
    cwd: Path | None = None,
) -> BuildConfig:
    """Combina las opciones (relativas a `cwd`) con `[tool.aurora.build]` (relativas al
    `pyproject.toml`) y valida el resultado. Las opciones ganan; `include` se suma."""
    cwd = (cwd or Path.cwd()).resolve()
    project = find_project(cwd)
    settings = load_settings(project)
    base = project or cwd

    def setting(key: str, kind: type) -> Any:
        value = settings.get(key)
        if value is not None and not isinstance(value, kind):
            raise BuildError(f"[tool.aurora.build] {key} debe ser {kind.__name__}, no {type(value).__name__}")
        return value

    if script is not None:
        script_path = cwd / script
    elif (configured := setting("script", str)) is not None:
        script_path = base / configured
    else:
        found = next((cwd / s for s in _DEFAULT_SCRIPTS if (cwd / s).is_file()), None)
        if found is None:
            raise BuildError(
                "no encuentro el script de la app: indícalo (`aurora build app.py`) "
                "o define `script` en [tool.aurora.build]"
            )
        script_path = found
    script_path = script_path.resolve()
    if not script_path.is_file():
        raise BuildError(f"el script {script_path} no existe")

    configured_include = setting("include", list) or []
    if not all(isinstance(p, str) for p in configured_include):
        raise BuildError("[tool.aurora.build] include debe ser una lista de rutas")
    includes = [(base / p).resolve() for p in configured_include]
    includes += [(cwd / p).resolve() for p in include or []]
    for path in includes:
        if not path.exists():
            raise BuildError(f"el recurso a incluir {path} no existe")

    icon_value = icon if icon is not None else setting("icon", str)
    icon_path = None
    if icon_value is not None:
        icon_path = ((cwd if icon is not None else base) / icon_value).resolve()
        if not icon_path.is_file():
            raise BuildError(f"el icono {icon_path} no existe")
        _check_icon(icon_path)

    dist_value = dist if dist is not None else setting("dist", str)
    dist_path = (cwd / dist).resolve() if dist is not None else (base / (dist_value or "dist")).resolve()

    final_name = name if name is not None else setting("name", str) or script_path.stem
    if not final_name.strip() or any(c in final_name for c in '/\\:*?"<>|'):
        raise BuildError(f"nombre de ejecutable inválido: {final_name!r}")

    return BuildConfig(
        script=script_path,
        name=final_name,
        root=base,
        dist=dist_path,
        icon=icon_path,
        include=includes,
        onefile=onefile if onefile is not None else _flag(setting("onefile", bool), True),
        console=console if console is not None else _flag(setting("console", bool), False),
        upx=upx if upx is not None else _flag(setting("upx", bool), False),
        clean=clean,
    )


def _flag(value: bool | None, default: bool) -> bool:
    return default if value is None else value


def _check_icon(path: Path) -> None:
    native = _NATIVE_ICON.get(sys.platform)
    if native is None or path.suffix.lower() == native:
        return  # Linux no incrusta iconos en el ejecutable: PyInstaller lo ignora.
    if importlib.util.find_spec("PIL") is None:
        raise BuildError(
            f"el icono {path.name} no es {native}: conviértelo o instala Pillow para que se convierta solo"
        )


def destination(path: Path, script: Path) -> str:
    """Carpeta (relativa al ejecutable) donde acaba un recurso incluido.

    Se conserva la ruta relativa al script, así `resource("assets/logo.png")` funciona igual al
    ejecutar con Python que empaquetado. Lo que está fuera de la carpeta del script va a la raíz.
    """
    try:
        relative = path.relative_to(script.parent)
    except ValueError:
        relative = Path(path.name)
    target = relative if path.is_dir() else relative.parent
    return target.as_posix() or "."


def pyinstaller_args(config: BuildConfig) -> list[str]:
    """Argumentos de PyInstaller para `config` (rutas absolutas: PyInstaller resuelve las
    relativas desde la carpeta del `.spec`, no desde donde se lanza)."""
    work = config.root / "build"
    args = [
        str(config.script),
        "--name",
        config.name,
        "--noconfirm",
        "--distpath",
        str(config.dist),
        "--workpath",
        str(work),
        "--specpath",
        str(work),
        "--onefile" if config.onefile and not config.app_bundle else "--onedir",
        "--console" if config.console else "--windowed",
        # Aurora no usa tkinter; PyInstaller lo incluiría si está instalado.
        "--exclude-module",
        "tkinter",
    ]
    if not config.upx:
        # UPX altera el binario (falsos positivos de antivirus, arranque más lento) y haría que
        # el build dependiera de tenerlo instalado: solo se usa pidiéndolo con `upx = true`.
        args.append("--noupx")
    if config.icon is not None:
        args += ["--icon", str(config.icon)]
    for path in config.include:
        args += ["--add-data", f"{path}{os.pathsep}{destination(path, config.script)}"]
    if config.clean:
        args.append("--clean")
    return args


def build(config: BuildConfig) -> Path:
    """Empaqueta la app y devuelve la ruta de lo que se distribuye."""
    if importlib.util.find_spec("PyInstaller") is None:
        raise BuildError(f"falta PyInstaller: {_INSTALL_HINT}")
    command = [sys.executable, "-m", "PyInstaller", *pyinstaller_args(config)]
    # Con `-m`, `--log-level` no filtra las líneas INFO del propio PyInstaller (ese código corre
    # como `__main__`, fuera del logger `PyInstaller`); por entorno, sí. Se respeta lo del usuario.
    env = os.environ.copy()
    env.setdefault("PYI_LOG_LEVEL", "WARN")
    result = subprocess.run(command, cwd=config.root, check=False, env=env)
    if result.returncode != 0:
        raise BuildError(f"PyInstaller terminó con código {result.returncode} (detalles arriba)")
    if not config.executable.exists():
        raise BuildError(f"PyInstaller terminó, pero no generó {config.executable}")
    return config.output
