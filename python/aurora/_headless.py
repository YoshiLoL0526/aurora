"""Ejecutar el script de una app sin abrir ventanas.

Lo comparten los comandos de comprobación del CLI (`aurora shot`, `tree`, `check` y `pilot`) y
los ejemplos vivos de la documentación (`docs/hooks/livedocs.py`): el script se ejecuta como
`python script.py` (`__main__`, `sys.argv` y `sys.path`), pero `App.run()` no abre nada, solo deja
la `App` a mano para renderizarla con un `Pilot`.

Los errores del código del usuario se convierten en `ScriptError`, que sabe señalar el archivo y
la línea del usuario sin la traza interna de Aurora.
"""

from __future__ import annotations

import ast
import sys
import sysconfig
import traceback
import types
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import DAYLIGHT, MIDNIGHT, App, Window
from . import reload as _reload
from ._core import Pilot
from .signal import Signal

_PACKAGE = Path(__file__).resolve().parent
# Código que no es del usuario: Aurora y la librería estándar o los paquetes instalados.
_LIBRARIES = {Path(sysconfig.get_path(name)).resolve() for name in ("stdlib", "purelib", "platlib")}


class UsageError(Exception):
    """La petición no tiene sentido para esta app (una ventana o un tema que no existen…)."""


@dataclass
class Location:
    """Un punto del código del usuario: archivo, línea y la línea de código."""

    file: str
    line: int | None = None
    code: str = ""

    def __str__(self) -> str:
        return f"{self.file}:{self.line}" if self.line else self.file


class ScriptError(Exception):
    """Una excepción del código del usuario (al importar el script, al construir la vista o en un
    manejador). `location` es el punto más interno del código del usuario, si lo hay."""

    def __init__(self, error: BaseException, location: Location | None = None) -> None:
        super().__init__(f"{type(error).__name__}: {error}")
        self.error = error
        self.location = location if location is not None else user_location(error)

    @property
    def kind(self) -> str:
        return type(self.error).__name__

    @property
    def message(self) -> str:
        return str(self.error) if not isinstance(self.error, SyntaxError) else self.error.msg

    def format(self, *, traceback_: bool = False) -> str:
        """El error en texto: `archivo:línea: Tipo: mensaje` y la línea de código (o la traza)."""
        if traceback_:
            return "".join(traceback.format_exception(self.error)).rstrip()
        head = f"{self.location}: " if self.location else ""
        lines = [f"{head}{self.kind}: {self.message}"]
        if self.location and self.location.code:
            lines.append(f"    {self.location.code}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        loc = self.location
        return {
            "type": self.kind,
            "message": self.message,
            "file": loc.file if loc else None,
            "line": loc.line if loc else None,
            "code": loc.code if loc else None,
        }


def _is_user(filename: str) -> bool:
    if filename.startswith("<"):
        return False  # código generado (`<string>`, `<frozen …>`)
    try:
        path = Path(filename).resolve()
    except OSError:
        return True
    if path.is_relative_to(_PACKAGE):
        return False
    return not any(path.is_relative_to(lib) for lib in _LIBRARIES)


def _shown_path(filename: str) -> str:
    """La ruta relativa a la carpeta actual si está dentro (más corta de leer); si no, tal cual."""
    try:
        return str(Path(filename).resolve().relative_to(Path.cwd()))
    except (OSError, ValueError):
        return filename


def user_location(error: BaseException) -> Location | None:
    """El punto más interno del código del usuario en la traza de `error`."""
    if isinstance(error, SyntaxError) and error.filename:
        return Location(_shown_path(error.filename), error.lineno, (error.text or "").strip())
    frames = traceback.extract_tb(error.__traceback__)
    for frame in reversed(frames):
        if _is_user(frame.filename):
            return Location(_shown_path(frame.filename), frame.lineno, (frame.line or "").strip())
    return None


@contextmanager
def as_main(module: types.ModuleType, script: str | None) -> Generator[None]:
    """Ejecuta como script principal: `__main__`, `sys.argv` y `sys.path` como `python script.py`."""
    saved_main, saved_argv, saved_path = sys.modules.get("__main__"), sys.argv, list(sys.path)
    sys.modules["__main__"] = module
    sys.argv = [script or module.__file__ or ""]
    if script:
        sys.path.insert(0, str(Path(script).resolve().parent))
    try:
        yield
    finally:
        if saved_main is not None:
            sys.modules["__main__"] = saved_main
        sys.argv = saved_argv
        sys.path[:] = saved_path


@contextmanager
def capturing() -> Generator[_reload._Context]:
    """Mientras dura, `App.run()` no abre ventana: la app queda en `context.ran` (y la última
    creada, en `context.created`). Es el mismo mecanismo que usa el hot reload."""
    context = _reload.context
    saved = context.active, context.created, context.ran
    context.active, context.created, context.ran = True, None, None
    try:
        yield context
    finally:
        context.active, context.created, context.ran = saved


def exec_source(source: str, filename: str, namespace: dict[str, Any]) -> Any:
    """Ejecuta `source` en `namespace`. Si termina en una expresión, devuelve su valor."""
    tree = ast.parse(source, filename=filename)
    last = tree.body[-1] if tree.body else None
    if isinstance(last, ast.Expr):
        tree.body.pop()  # la última expresión se evalúa aparte: puede ser lo que se dibuja
    else:
        last = None
    exec(compile(tree, filename, "exec"), namespace)
    if last is None:
        return None
    return eval(compile(ast.Expression(last.value), filename, "eval"), namespace)


def load(script: str | Path) -> App:
    """Ejecuta `script` como `python script.py` sin abrir ventanas y devuelve su `App`.

    La que ejecuta con `run()` o, si no llega a ejecutar ninguna (p. ej. la crea pero la arranca
    otro módulo), la última que crea. `ScriptError` si el script falla; `UsageError` si no crea
    ninguna `App`.
    """
    path = Path(script)
    if not path.is_file():
        raise UsageError(f"no existe el script {script}")
    filename = str(path.resolve())
    module = types.ModuleType("__main__")
    module.__file__ = filename
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise UsageError(f"no se pudo leer {script}: {e}") from e
    with as_main(module, filename), capturing() as context:
        try:
            exec_source(source, filename, module.__dict__)
        except SystemExit as e:
            # `sys.exit()` tras crear la app (p. ej. `sys.exit(app.run())`) no es un fallo.
            if context.ran is None and context.created is None:
                raise UsageError(f"el script terminó con sys.exit({e.code!r}) sin crear ninguna App") from e
        except Exception as e:
            raise ScriptError(e) from e
        app = context.ran or context.created
    if not isinstance(app, App):
        raise UsageError(f"{script} no crea ninguna App (aurora.App(view))")
    return app


def windows(app: App) -> list[Window]:
    """La principal y las adicionales de `app`, en orden."""
    return app._all_windows()


def pick_window(app: App, which: str | None) -> Window:
    """La ventana `which` de la app: su número (0 es la principal) o su título (exacto o, si es
    único, una parte, sin distinguir mayúsculas). Sin `which`, la principal."""
    every = windows(app)
    if which is None:
        return every[0]
    if which.isdigit():
        found = [w for w in every if w._id == int(which)]
    else:
        found = [w for w in every if w.title == which] or [
            w for w in every if which.casefold() in w.title.casefold()
        ]
    if len(found) == 1:
        return found[0]
    listed = ", ".join(f"{w._id} ({w.title!r})" for w in every)
    what = "varias ventanas coinciden con" if found else "no hay ninguna ventana"
    raise UsageError(f"{what} {which!r}; las de la app: {listed}")


def apply_theme(app: App, theme: str | None) -> None:
    """Fuerza el tema claro (`"light"`) u oscuro (`"dark"`) si la app usa los de Aurora: un tema
    `DAYLIGHT`/`MIDNIGHT` o un `Signal` que guarda uno de los dos (el interruptor habitual)."""
    if theme is None:
        return
    wanted = DAYLIGHT if theme == "light" else MIDNIGHT
    current = app.theme
    if current is MIDNIGHT or current is DAYLIGHT:
        app.theme = wanted
    elif isinstance(current, Signal) and current.value in (MIDNIGHT, DAYLIGHT):
        current.set(wanted)
    else:
        raise UsageError(
            "la app usa un tema propio: --theme solo alterna entre DAYLIGHT y MIDNIGHT "
            "(un tema fijo o un Signal con uno de ellos)"
        )


def start(
    window: Window,
    *,
    size: tuple[float, float] | None = None,
    scale: float = 1.0,
) -> Pilot:
    """Un `Pilot` de `window` con el primer frame ya asentado (sin transiciones en curso).

    `ScriptError` si la vista falla al construirse.
    """
    try:
        pilot = window.pilot(size=size, scale=scale)
        pilot.settle()
    except Exception as e:
        raise ScriptError(e) from e
    return pilot
