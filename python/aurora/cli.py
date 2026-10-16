"""Línea de comandos de Aurora: `aurora dev` y `aurora build` (también `python -m aurora`)."""

from __future__ import annotations

import argparse
import os
import runpy
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .build import BuildError, build, resolve


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aurora", description="Herramientas de Aurora.")
    parser.add_argument("--version", action="version", version=f"aurora {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="comando")

    d = commands.add_parser(
        "dev",
        help="ejecuta la app con hot reload",
        description="Ejecuta la app con hot reload: al guardar el script o un módulo local, la ventana "
        "se actualiza con el código nuevo y conserva el estado de los Signal.",
    )
    d.add_argument("script", help="script de la app")
    d.add_argument("--inspector", action="store_true", help="permitir abrir el inspector con F12")
    d.add_argument("args", nargs=argparse.REMAINDER, help="argumentos para el script")

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
    p.add_argument("--dist", help="carpeta de salida (por defecto: dist)")
    p.add_argument("--clean", action="store_true", help="borrar la caché de PyInstaller antes")

    args = parser.parse_args(argv)
    if args.command == "dev":
        return dev(args.script, args.args, inspector=args.inspector)
    try:
        config = resolve(
            args.script,
            name=args.name,
            icon=args.icon,
            include=args.include,
            onefile=args.onefile,
            console=args.console,
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
