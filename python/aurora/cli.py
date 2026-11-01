"""Línea de comandos de Aurora (también `python -m aurora`).

Cada subcomando se registra con su función `_add_<nombre>` y se ejecuta con la que guarda en
`run`: para añadir uno, basta con otra `_add_…` en `COMMANDS`.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import runpy
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

from . import __version__
from .build import BuildError, build, resolve

if TYPE_CHECKING:
    from . import Window
    from ._core import Pilot


def main(argv: Sequence[str] | None = None) -> int:
    # La ayuda y los errores de uso de argparse también llevan tildes: sin esto, en una tubería
    # de Windows salen en la página de códigos local y se leen rotos (`documentaci�n`).
    _utf8(sys.stdout)
    _utf8(sys.stderr)
    parser = argparse.ArgumentParser(prog="aurora", description="Herramientas de Aurora.")
    parser.add_argument("--version", action="version", version=f"aurora {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="comando")
    for add in COMMANDS:
        add(commands)
    args = parser.parse_args(argv)
    return args.run(args)


def _add_dev(commands: argparse._SubParsersAction) -> None:
    d = commands.add_parser(
        "dev",
        help="ejecuta la app con hot reload",
        description="Ejecuta la app con hot reload: al guardar el script o un módulo local, la ventana "
        "se actualiza con el código nuevo y conserva el estado de los Signal.",
    )
    d.add_argument("script", help="script de la app")
    d.add_argument("--inspector", action="store_true", help="permitir abrir el inspector con F12")
    d.add_argument("args", nargs=argparse.REMAINDER, help="argumentos para el script")
    d.set_defaults(run=lambda args: dev(args.script, args.args, inspector=args.inspector))


def _add_build(commands: argparse._SubParsersAction) -> None:
    p = commands.add_parser(
        "build",
        help="empaqueta la app en un ejecutable",
        description="Empaqueta la app en un ejecutable distribuible (con PyInstaller). Las opciones "
        "tienen prioridad sobre [tool.aurora.build] de pyproject.toml.",
    )
    p.add_argument("script", nargs="?", help="script de la app (por defecto: main.py o app.py)")
    p.add_argument("--name", help="nombre del ejecutable (por defecto: el del script)")
    p.add_argument("--icon", help="icono: .ico en Windows, .icns en macOS (otros, con Pillow)")
    p.add_argument(
        "--include",
        action="append",
        metavar="RUTA",
        help="archivo o carpeta que se copia junto a la app (repetible)",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--onefile", action="store_true", default=None, help="un solo archivo (por defecto)")
    mode.add_argument("--onedir", dest="onefile", action="store_false", help="una carpeta (arranca antes)")
    window = p.add_mutually_exclusive_group()
    window.add_argument("--console", action="store_true", default=None, help="mantener la consola")
    window.add_argument("--windowed", dest="console", action="store_false", help="sin consola (por defecto)")
    upx = p.add_mutually_exclusive_group()
    upx.add_argument(
        "--upx",
        action="store_true",
        default=None,
        help="comprimir los binarios con UPX (más pequeño; requiere UPX y puede disparar antivirus)",
    )
    upx.add_argument("--no-upx", dest="upx", action="store_false", help="no comprimir con UPX (por defecto)")
    p.add_argument("--dist", help="carpeta de salida (por defecto: dist)")
    p.add_argument("--clean", action="store_true", help="borrar la caché de PyInstaller antes")
    p.set_defaults(run=_build)


def _build(args: argparse.Namespace) -> int:
    try:
        config = resolve(
            args.script,
            name=args.name,
            icon=args.icon,
            include=args.include,
            onefile=args.onefile,
            console=args.console,
            upx=args.upx,
            dist=args.dist,
            clean=args.clean,
        )
        print(f"Empaquetando {config.script.name} en {config.name}...", flush=True)
        output = build(config)
    except BuildError as e:
        print(f"aurora build: error: {e}", file=sys.stderr)
        return 1
    print(f"Listo: {output}")
    return 0


def dev(script: str, args: Sequence[str] = (), *, inspector: bool = False) -> int:
    """Ejecuta `script` como `python script`, con el hot reload (y quizá el inspector) activado."""
    path = Path(script)
    if not path.is_file():
        print(f"aurora dev: error: no existe el script {script}", file=sys.stderr)
        return 1
    os.environ["AURORA_RELOAD"] = "1"
    if inspector:
        os.environ["AURORA_INSPECTOR"] = "1"
    # Como `python script`: su carpeta va primero en sys.path, para sus módulos locales.
    sys.argv = [str(path), *args]
    sys.path.insert(0, str(path.resolve().parent))
    runpy.run_path(str(path), run_name="__main__")
    return 0


def _add_docs(commands: argparse._SubParsersAction) -> None:
    p = commands.add_parser(
        "docs",
        help="imprime la documentación de esta versión (para agentes y modelos)",
        description="Imprime en Markdown plano la documentación de la versión instalada, pensada para "
        "que la lea un agente o un modelo de lenguaje. Sin argumentos, la chuleta: el modelo mental, "
        "las firmas, las props de estilo, los tokens y los errores frecuentes.",
    )
    p.add_argument("topic", nargs="*", metavar="tema", help="sección de la referencia: button, pilot, style…")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--search", metavar="TEXTO", help="lista las secciones que contienen el texto")
    mode.add_argument(
        "--full", action="store_true", help="toda la documentación: chuleta, guía, recetas y referencia"
    )
    mode.add_argument("--list", action="store_true", help="lista los temas disponibles")
    p.set_defaults(run=_docs)


def _docs(args: argparse.Namespace) -> int:
    from . import _llmdocs

    if args.topic and (args.search or args.full or args.list):
        return _fail("aurora docs: error: un tema no se combina con --search, --full ni --list", 2)
    if args.full:
        _emit(_llmdocs.full(__version__))
    elif args.list:
        lines = [f"# Temas de `aurora docs` (Aurora {__version__})", ""]
        for section in _llmdocs.sections():
            if section.page == "reference.md" and section.level in (2, 3):
                lines.append(f"{'  ' * (section.level - 2)}- {_llmdocs.command(section)}: {section.title}")
        _emit("\n".join(lines) + "\n")
    elif args.search is not None:
        hits = _llmdocs.search(args.search)
        if not hits:
            return _fail(f"aurora docs: nada contiene {args.search!r}")
        lines = [f"# Secciones que contienen {args.search!r}", ""]
        for section, line in hits:
            where = f"{_llmdocs.page_title(section.page)} › {' › '.join(section.path[1:])}"
            lines.append(f"- {where} (`{_llmdocs.command(section)}`)")
            if line:
                lines.append(f"  > {line[:160]}")
        _emit("\n".join(lines) + "\n")
    elif args.topic:
        name = " ".join(args.topic)
        section = _llmdocs.find(name)
        if section is None:
            close = _llmdocs.suggest(name)
            hint = f" ¿Quisiste decir {' o '.join(repr(c) for c in close)}?" if close else ""
            return _fail(
                f"aurora docs: no hay ningún tema {name!r}.{hint} Prueba `aurora docs --search {name}` "
                "o `aurora docs --list`."
            )
        _emit(section.text)
    else:
        _emit(_llmdocs.cheatsheet(__version__))
    return 0


def _emit(text: str) -> None:
    """Escribe Markdown a stdout en UTF-8."""
    stream = _utf8(sys.stdout)
    stream.write(text)
    stream.flush()


def _fail(message: str, code: int = 1) -> int:
    print(message, file=_utf8(sys.stderr))
    return code


def _utf8(stream: TextIO) -> TextIO:
    """`stream` en UTF-8: redirigida a una tubería en Windows usaría la página de códigos local,
    que no tiene `→` ni `›` (y un agente siempre lee así)."""
    if isinstance(stream, io.TextIOWrapper) and stream.encoding.lower().replace("-", "") != "utf8":
        stream.flush()
        stream.reconfigure(encoding="utf-8")
    return stream


def _add_agents(commands: argparse._SubParsersAction) -> None:
    p = commands.add_parser(
        "agents",
        help="escribe en AGENTS.md cómo trabajar con Aurora (para agentes de programación)",
        description="Escribe en el AGENTS.md del proyecto una sección que explica a un agente de "
        "programación cómo consultar la documentación de esta versión (`aurora docs`) y comprobar su "
        "trabajo sin ventana. Si el archivo existe, añade la sección al final o sustituye la que "
        "escribió antes; no toca el resto.",
    )
    p.add_argument(
        "path", nargs="?", default=".", help="carpeta del proyecto o ruta del archivo (por defecto: .)"
    )
    p.add_argument(
        "--force", action="store_true", help="sobrescribir el archivo entero en vez de añadir la sección"
    )
    p.add_argument("--print", action="store_true", help="imprimir la sección en vez de escribirla")
    p.set_defaults(run=_agents)


def _agents(args: argparse.Namespace) -> int:
    from . import _agents as agents

    if args.print:
        _emit(agents.section(__version__))
        return 0
    path = Path(args.path)
    if path.is_dir() or not path.suffix:
        path = path / "AGENTS.md"
    if not path.parent.is_dir():
        return _fail(f"aurora agents: error: no existe la carpeta {path.parent}")
    action = agents.write(path, __version__, force=args.force)
    print(f"{path}: {action}")
    return 0


# ---------------------------------------------------------------------------
# Comprobar sin ventana: `aurora shot`, `tree`, `check` y `pilot` (para agentes).
#
# La lógica vive en `_headless` (ejecutar el script), `_tree` (árbol y avisos) y `_script` (guiones
# de `pilot`); aquí solo se leen las opciones y se presenta el resultado. Códigos de salida: 0 bien,
# 1 la app falla (o un aviso con `--strict`, o un paso del guion), 2 uso incorrecto.


def _size_arg(value: str) -> tuple[float, float]:
    try:
        w, h = (float(v) for v in value.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} no es ANCHOxALTO (p. ej. 800x600)") from None
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("el tamaño debe ser positivo")
    return w, h


def _positive(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} no es un número") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("debe ser mayor que 0")
    return number


def _depth(value: str) -> int:
    if not value.isdigit():
        raise argparse.ArgumentTypeError(f"{value!r} no es un entero >= 0")
    return int(value)


def _add_target(p: argparse.ArgumentParser) -> None:
    """Opciones comunes de los comandos que ejecutan una app sin ventana."""
    p.add_argument("script", help="script de la app (se ejecuta como `python script`, sin abrir ventanas)")
    p.add_argument(
        "--size", type=_size_arg, metavar="ANCHOxALTO", help="tamaño de la ventana (por defecto: el suyo)"
    )
    p.add_argument("--theme", choices=["light", "dark"], help="fuerza el tema claro u oscuro de Aurora")
    p.add_argument("--window", metavar="ID|TÍTULO", help="ventana de una app con varias (0: la principal)")
    p.add_argument("--json", action="store_true", help="salida en JSON")
    p.add_argument("--traceback", action="store_true", help="traza completa de los errores, con la de Aurora")


class _Target:
    """La app de un comando ya cargada: su ventana, el tamaño y un `Pilot` con el primer frame."""

    def __init__(self, window: Window, size: tuple[float, float], pilot: Pilot) -> None:
        self.window, self.size, self.pilot = window, size, pilot

    def info(self) -> dict[str, Any]:
        w = self.window
        return {"id": w._id, "title": w.title, "size": list(self.size)}


def _open(args: argparse.Namespace, *, scale: float = 1.0) -> _Target:
    """Carga el script y arranca su ventana sin abrirla. Lanza `UsageError` o `ScriptError`."""
    from . import _headless

    # Lo que imprima el script va a stderr: stdout es para el resultado (y el JSON).
    with contextlib.redirect_stdout(sys.stderr):
        app = _headless.load(args.script)
        window = _headless.pick_window(app, args.window)
        _headless.apply_theme(app, args.theme)
        size = args.size or window.size
        return _Target(window, size, _headless.start(window, size=size, scale=scale))


def _failure(args: argparse.Namespace, error: Exception, data: dict[str, Any] | None = None) -> int:
    """Presenta un error de `_open` (o de un comando) y devuelve su código de salida."""
    from ._headless import ScriptError, UsageError

    name = f"aurora {args.command}"
    if isinstance(error, UsageError):
        code, payload = 2, {"type": "UsageError", "message": str(error)}
        text = f"{name}: error: {error}"
    elif isinstance(error, LookupError):
        code, payload = 1, {"type": "LookupError", "message": str(error.args[0] if error.args else error)}
        text = f"{name}: error: {payload['message']}"
    elif isinstance(error, ScriptError):
        code, payload = 1, error.to_dict()
        text = f"{name}: la app falla\n{error.format(traceback_=args.traceback)}"
    else:
        raise error
    if args.json:
        _json({"ok": False, **(data or {}), "error": payload})
    else:
        print(text, file=_utf8(sys.stderr))
    return code


def _json(data: dict[str, Any]) -> None:
    _emit(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _add_shot(commands: argparse._SubParsersAction) -> None:
    p = commands.add_parser(
        "shot",
        help="renderiza la app a PNG sin abrir ventana",
        description="Ejecuta la app sin ventana, renderiza su primer frame (ya sin transiciones) a PNG "
        "e imprime la ruta escrita. Con --key, solo la caja de ese nodo.",
    )
    _add_target(p)
    p.add_argument("-o", "--output", metavar="RUTA", help="PNG de salida (por defecto: <script>-shot.png)")
    p.add_argument(
        "--scale", type=_positive, default=1.0, help="densidad de píxeles (2 = Retina; por defecto 1)"
    )
    p.add_argument("--key", help="recorta la captura a la caja de este nodo")
    p.set_defaults(run=_shot)


def _shot(args: argparse.Namespace) -> int:
    from ._headless import ScriptError, UsageError
    from ._tree import snapshot

    output = Path(args.output or f"{Path(args.script).stem}-shot.png")
    if not output.parent.is_dir():
        return _failure(args, UsageError(f"no existe la carpeta {output.parent}"))
    try:
        target = _open(args, scale=args.scale)
        if args.key is not None:
            snap = snapshot(target.pilot, target.size)
            if snap.find(args.key) is None:
                return _failure(args, LookupError(snap.missing(args.key)))
        target.pilot.png(os.fspath(output), args.key)
    except (UsageError, ScriptError) as e:
        return _failure(args, e)
    if args.json:
        _json(
            {
                "ok": True,
                "path": str(output.resolve()),
                "window": target.info(),
                "scale": args.scale,
                "key": args.key,
            }
        )
    else:
        _emit(f"{output}\n")
    return 0


def _add_tree(commands: argparse._SubParsersAction) -> None:
    p = commands.add_parser(
        "tree",
        help="imprime el árbol pintado de la app, con avisos de layout",
        description="Ejecuta la app sin ventana e imprime su árbol pintado en texto indentado: tipo o "
        "rol, texto o nombre accesible, #key, caja @x,y anchoxalto y estados. Se omiten los "
        "contenedores anónimos (sin key, rol ni interacción). Al final, los avisos de layout.",
    )
    _add_target(p)
    p.add_argument("--depth", type=_depth, metavar="N", help="niveles que se muestran (por defecto: todos)")
    p.add_argument("--key", help="solo el subárbol de este nodo")
    p.set_defaults(run=_tree_command)


def _tree_command(args: argparse.Namespace) -> int:
    from . import _tree
    from ._headless import ScriptError, UsageError

    try:
        target = _open(args)
    except (UsageError, ScriptError) as e:
        return _failure(args, e)
    snap = _tree.snapshot(target.pilot, target.size)
    root = snap.root
    if args.key is not None:
        node = snap.find(args.key)
        if node is None:
            return _failure(args, LookupError(snap.missing(args.key)))
        root = node
    inside = {n.key for n in root.walk()}
    found = [w for w in snap.warnings() if w.key in inside]
    if args.json:
        _json(
            {
                "ok": True,
                "window": target.info(),
                "focused": snap.focused,
                "tree": root.to_dict(args.depth),
                "warnings": [w.to_dict() for w in found],
            }
        )
    else:
        _emit(f"{_tree.format_tree(root, depth=args.depth)}\n\n{_tree.format_warnings(found)}\n")
    return 0


def _add_check(commands: argparse._SubParsersAction) -> None:
    p = commands.add_parser(
        "check",
        help="comprueba que la app construye y pinta su vista, y avisa de problemas de layout",
        description="Ejecuta la app sin ventana, construye y pinta un frame y sale con 0 si todo va bien. "
        "Si el script o la vista lanzan una excepción, imprime el error con el archivo y la línea de "
        "tu código (sin la traza de Aurora, salvo con --traceback) y sale con 1. Muestra los avisos "
        "de `aurora tree`; con --strict, un aviso también es un fallo.",
    )
    _add_target(p)
    p.add_argument("--strict", action="store_true", help="los avisos de layout también hacen fallar")
    p.set_defaults(run=_check)


def _check(args: argparse.Namespace) -> int:
    from . import _tree
    from ._headless import ScriptError, UsageError

    try:
        target = _open(args)
    except (UsageError, ScriptError) as e:
        return _failure(args, e, {"script": args.script})
    snap = _tree.snapshot(target.pilot, target.size)
    found = snap.warnings()
    ok = not (args.strict and found)
    if args.json:
        _json(
            {
                "ok": ok,
                "script": args.script,
                "window": target.info(),
                "nodes": len(snap.by_key),
                "warnings": [w.to_dict() for w in found],
                "error": None,
            }
        )
    else:
        w, h = target.size
        verdict = "ok" if ok else "falla (--strict: hay avisos)"
        lines = [f"{args.script}: {verdict} — {target.window.title!r}, {w:g}x{h:g}, {len(snap.by_key)} nodos"]
        if found:
            lines.append(_tree.format_warnings(found))
        _emit("\n".join(lines) + "\n")
    return 0 if ok else 1


def _add_pilot(commands: argparse._SubParsersAction) -> None:
    from ._script import usage

    p = commands.add_parser(
        "pilot",
        help="ejecuta un guion de interacción (clics, teclas, capturas) sin abrir ventana",
        description="Ejecuta la app sin ventana y le aplica un guion de pasos separados por `;` o por "
        "líneas, como `click add; type hola; press enter; shot out.png; tree`. Cada paso espera a que "
        "acaben las transiciones. Se para en el primer paso que falla y dice cuál (sale con 1).",
        epilog=f"Comandos del guion:\n{usage()}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_target(p)
    p.add_argument("steps", nargs="?", metavar="pasos", help="el guion, entre comillas")
    p.add_argument(
        "--script", dest="steps_file", metavar="ARCHIVO", help="lee el guion de un archivo (- es stdin)"
    )
    p.add_argument(
        "--scale", type=_positive, default=1.0, help="densidad de píxeles de `shot` (por defecto 1)"
    )
    p.set_defaults(run=_pilot)


def _read_steps(args: argparse.Namespace) -> str:
    """El texto del guion (de la línea de comandos, de un archivo o de stdin). `UsageError` si no."""
    from ._headless import UsageError

    if (args.steps is None) == (args.steps_file is None):
        raise UsageError("indica el guion entre comillas o con --script ARCHIVO (uno de los dos)")
    if args.steps_file is None:
        return args.steps
    try:
        if args.steps_file == "-":
            return sys.stdin.read()
        return Path(args.steps_file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise UsageError(f"no se pudo leer el guion: {e}") from e


def _pilot(args: argparse.Namespace) -> int:
    from . import _script
    from ._headless import ScriptError, UsageError

    try:
        steps = _script.parse(_read_steps(args))
        target = _open(args, scale=args.scale)
    except _script.ScriptSyntaxError as e:
        return _failure(args, UsageError(str(e)))
    except (UsageError, ScriptError) as e:
        return _failure(args, e)
    out = _utf8(sys.stdout)
    with contextlib.redirect_stdout(sys.stderr):
        results = list(_script.Runner(target.pilot, target.size).run(steps))
    for result in results:
        if args.json or not result.ok:
            continue
        out.write(f"[{result.step.number}] {result.step.source}\n")
        if result.output:
            out.write("".join(f"    {ln}\n" for ln in result.output.splitlines()))
        out.flush()
    failed = next((r for r in results if not r.ok), None)
    if args.json:
        _json({"ok": failed is None, "window": target.info(), "steps": [r.to_dict() for r in results]})
    elif failed is not None:
        error = failed.error or ""
        if args.traceback and failed.script_error is not None:
            error = failed.script_error.format(traceback_=True)
        step = failed.step
        print(f"aurora pilot: falló el paso {step.number} ({step.source}):\n{error}", file=_utf8(sys.stderr))
    else:
        out.write(f"ok: {len(results)} pasos\n")
        out.flush()
    return 0 if failed is None else 1


COMMANDS = [_add_dev, _add_build, _add_docs, _add_agents, _add_shot, _add_tree, _add_check, _add_pilot]
