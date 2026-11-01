"""Línea de comandos de Aurora (también `python -m aurora`).

Cada subcomando se registra con su función `_add_<nombre>` y se ejecuta con la que guarda en
`run`: para añadir uno, basta con otra `_add_…` en `COMMANDS`.
"""

from __future__ import annotations

import argparse
import io
import os
import runpy
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from . import __version__
from .build import BuildError, build, resolve


def main(argv: Sequence[str] | None = None) -> int:
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


COMMANDS = [_add_dev, _add_build, _add_docs, _add_agents]
