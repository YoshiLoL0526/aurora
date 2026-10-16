"""Ejemplos vivos de la documentación.

Un bloque de código marcado como ```` ```python live ```` se ejecuta al construir la
documentación, y debajo de su código se inserta la captura de lo que dibuja, renderizada por la
propia Aurora. Así cada ejemplo publicado se ha ejecutado de verdad con la versión que se publica:
si deja de funcionar, la documentación no se construye (y `tests/test_docs.py` falla).

Qué se renderiza, en este orden:

1. La última `App` que el bloque crea y ejecuta (`App(view).run()` no abre ventana aquí).
2. Si el bloque termina en una expresión que da un `Element` (o una lista de ellos), ese
   fragmento sobre el fondo del tema, con el alto justo de su contenido.
3. Con `continue`, la `view` que defina el bloque, con el tamaño y el tema de la app anterior.

Atributos tras `live` (separados por espacios, con comillas si hace falta):

- `continue`: se ejecuta en el espacio de nombres del bloque vivo anterior de la página (para
  pasos que añaden código al programa de antes).
- `size=900x600`: tamaño de la ventana (sustituye al de la `App`); en un fragmento, `size=480`
  fija el ancho máximo (640 por defecto) y la captura se ajusta a su contenido.
- `align=stretch`: alineación de un fragmento en su columna (`start` por defecto).
- `file=examples/hello.py`: ejecuta ese archivo como script principal y muestra solo su captura;
  el cuerpo del bloque, si lo hay, se ejecuta después sin mostrarse (para preparar un estado).
- `theme=dark` o `theme=light`: una sola captura con ese tema (para apps con colores propios
  pensados para uno de los dos).
- `alt="…"`: texto alternativo de la captura.

Las líneas que terminan en `# oculto`, y las que van entre `# oculto: inicio` y `# oculto: fin`,
se ejecutan pero no se muestran (para preparar datos o un estado sin distraer del ejemplo). Si la
app no fija otro tema que el de por defecto, se renderiza en claro y en oscuro, y la documentación
enseña la del tema del lector.

El módulo no depende de MkDocs: `mkdocs_hooks.py` lo conecta con el sitio.
"""

from __future__ import annotations

import ast
import hashlib
import math
import os
import posixpath
import re
import shlex
import sys
import traceback
import types
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aurora import DAYLIGHT, MIDNIGHT, App, Element, column, row
from aurora import reload as _reload

ROOT = Path(__file__).resolve().parents[2]
"""Raíz del repositorio: las rutas de `file=` se resuelven desde aquí."""
DOCS = ROOT / "docs"

SCALE = 2.0  # densidad de las capturas (nítidas en pantallas Retina)
FRAGMENT_WIDTH = 640
FRAGMENT_PADDING = 24
LIVE_KEY = "__live__"
HIDDEN = "# oculto"
HIDDEN_START, HIDDEN_END = "# oculto: inicio", "# oculto: fin"

_OPEN = re.compile(
    r"^(?P<indent>[ \t]*)(?P<fence>`{3,}|~{3,})[ \t]*python[ \t]+live(?:[ \t]+(?P<attrs>.*))?$"
)
_SIZE = re.compile(r"^(\d+)(?:x(\d+))?$")
_ATTRS = {"continue", "size", "align", "file", "theme", "alt"}


class LiveError(Exception):
    """Un ejemplo vivo no se pudo ejecutar o renderizar. El mensaje lleva página y línea."""


@dataclass
class Block:
    """Un bloque ```` ```python live ```` de una página."""

    page: str
    line: int  # línea de la apertura, desde 1
    start: int  # índices de línea de la apertura y del cierre
    end: int
    indent: str
    fence: str
    code: str  # el cuerpo tal cual (sin la sangría del bloque)
    attrs: dict[str, str] = field(default_factory=dict)

    @property
    def where(self) -> str:
        return f"{self.page}:{self.line}"

    @property
    def shown(self) -> str:
        """El código que se muestra: sin lo oculto ni los huecos que deja al principio y al final."""
        shown: list[str] = []
        hiding = False
        for ln in self.code.splitlines():
            mark = ln.strip()
            if mark in (HIDDEN_START, HIDDEN_END):
                hiding = mark == HIDDEN_START
            elif not hiding and not mark.endswith(HIDDEN):
                shown.append(ln)
        return re.sub(r"\n{4,}", "\n\n\n", "\n".join(shown)).strip("\n")


@dataclass
class Shot:
    """Una captura generada: `uri` relativa a la carpeta de la documentación."""

    uri: str
    path: Path
    theme: str = ""  # "light", "dark" o "" (una sola captura)


@dataclass
class _Session:
    """Estado de una página: el espacio de nombres y la app del último bloque vivo."""

    module: types.ModuleType | None = None
    app: App | None = None


def find_blocks(text: str, page: str) -> list[Block]:
    """Los bloques vivos de una página Markdown, en orden."""
    lines = text.splitlines()
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        m = _OPEN.match(lines[i])
        if not m:
            i += 1
            continue
        indent, fence = m["indent"], m["fence"]
        close = re.compile(rf"^{re.escape(indent)}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*$")
        end = next((j for j in range(i + 1, len(lines)) if close.match(lines[j])), None)
        if end is None:
            raise LiveError(f"{page}:{i + 1}: bloque vivo sin cerrar")
        body = [ln[len(indent) :] if ln.startswith(indent) else ln.lstrip() for ln in lines[i + 1 : end]]
        block = Block(page, i + 1, i, end, indent, fence, "\n".join(body), _parse_attrs(m["attrs"] or ""))
        _check_attrs(block)
        marks = [ln.strip() for ln in body if ln.strip() in (HIDDEN_START, HIDDEN_END)]
        if marks != [HIDDEN_START, HIDDEN_END] * (len(marks) // 2) or len(marks) % 2:
            raise LiveError(f"{block.where}: cada `{HIDDEN_START}` necesita su `{HIDDEN_END}`, sin anidar")
        blocks.append(block)
        i = end + 1
    return blocks


def _parse_attrs(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for token in shlex.split(raw):
        name, _, value = token.partition("=")
        attrs[name] = value
    return attrs


def _check_attrs(block: Block) -> None:
    unknown = set(block.attrs) - _ATTRS
    if unknown:
        raise LiveError(
            f"{block.where}: atributo desconocido {sorted(unknown)[0]!r} (válidos: {sorted(_ATTRS)})"
        )
    size = block.attrs.get("size")
    if size is not None and not _SIZE.match(size):
        raise LiveError(f"{block.where}: size={size!r} no es ANCHO o ANCHOxALTO (p. ej. 900x600)")
    align = block.attrs.get("align")
    if align is not None and align not in ("start", "center", "end", "stretch"):
        raise LiveError(f"{block.where}: align={align!r} debe ser start, center, end o stretch")
    theme = block.attrs.get("theme")
    if theme is not None and theme not in ("light", "dark"):
        raise LiveError(f"{block.where}: theme={theme!r} debe ser light o dark")
    if "file" in block.attrs and not (ROOT / block.attrs["file"]).is_file():
        raise LiveError(f"{block.where}: file={block.attrs['file']!r} no existe")


def render_page(text: str, page: str, out_dir: Path) -> tuple[str, list[Shot]]:
    """Ejecuta los bloques vivos de `page` (ruta relativa a la documentación, con `/`).

    Escribe las capturas en `out_dir/_live/` y devuelve el Markdown con cada bloque seguido de
    sus imágenes (enlazadas de forma relativa a la página), y las capturas generadas.
    """
    blocks = find_blocks(text, page)
    if not blocks:
        return text, []
    lines = text.splitlines()
    session = _Session()
    shots: list[Shot] = []
    out: list[str] = []
    prev = 0
    for index, block in enumerate(blocks):
        made = run_block(block, session, out_dir, index)
        shots.extend(made)
        out.extend(lines[prev : block.start])
        if "file" not in block.attrs:
            out.append(f"{block.indent}{block.fence}python")
            out.extend(f"{block.indent}{ln}" if ln else "" for ln in block.shown.splitlines())
            out.append(f"{block.indent}{block.fence}")
            out.append("")
        out.extend(f"{block.indent}{_image_markdown(shot, page, block)}" for shot in made)
        prev = block.end + 1
    out.extend(lines[prev:])
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), shots


def _image_markdown(shot: Shot, page: str, block: Block) -> str:
    link = posixpath.relpath(shot.uri, posixpath.dirname(page) or ".")
    # Material oculta las `#only-light` en tema oscuro y viceversa.
    variant = f"#only-{shot.theme}" if shot.theme else ""
    alt = block.attrs.get("alt", "Resultado del ejemplo, renderizado por Aurora")
    width = _shot_width(shot.path)
    return f'![{alt}]({link}{variant}){{ .live width="{width}" loading=lazy }}'


def _shot_width(path: Path) -> int:
    """Ancho lógico de un PNG (el de la cabecera IHDR entre la escala)."""
    with path.open("rb") as f:
        header = f.read(24)
    return round(int.from_bytes(header[16:20], "big") / SCALE)


def run_block(block: Block, session: _Session, out_dir: Path, index: int) -> list[Shot]:
    """Ejecuta un bloque y renderiza lo que produce. Devuelve sus capturas."""
    try:
        app, fragment = _execute(block, session)
        return _render(block, app, fragment, out_dir, index)
    except LiveError:
        raise
    except Exception as e:
        details = "".join(traceback.format_exception(e)).rstrip()
        raise LiveError(f"{block.where}: el ejemplo vivo falló\n{details}") from e


def _execute(block: Block, session: _Session) -> tuple[App, bool]:
    """Ejecuta el bloque. Devuelve la app que hay que renderizar y si es un fragmento."""
    file = block.attrs.get("file")
    fresh = "continue" not in block.attrs or session.module is None
    module = types.ModuleType("__main__") if fresh else session.module
    assert module is not None
    filename = str(ROOT / file) if file else f"<{block.where}>"
    module.__file__ = filename if file else str(DOCS / block.page)
    if fresh:
        session.app = None
    session.module = module

    sources = [(Path(filename).read_text(encoding="utf-8"), filename)] if file else []
    sources.append((block.code, f"<{block.where}>"))
    value: Any = None
    ran: App | None = None
    with _as_main(module, filename if file else None):
        for source, name in sources:
            tree = ast.parse(source, filename=name)
            last = tree.body[-1] if tree.body else None
            if isinstance(last, ast.Expr):
                tree.body.pop()  # la última expresión se evalúa aparte: puede ser lo que se dibuja
            else:
                last = None
            _reload.context.active, _reload.context.created, _reload.context.ran = True, None, None
            try:
                exec(compile(tree, name, "exec"), module.__dict__)
                if last is not None:
                    expr = ast.Expression(last.value)
                    value = eval(compile(expr, name, "eval"), module.__dict__)
                ran = _reload.context.ran or ran
            finally:
                _reload.context.active, _reload.context.created, _reload.context.ran = False, None, None

    if ran is not None:
        session.app = ran
        return ran, False
    items = value if isinstance(value, (list, tuple)) else [value]
    if value is not None and all(isinstance(v, Element) for v in items):
        return _fragment(block, items), True
    view = module.__dict__.get("view")
    if not fresh and session.app is not None and callable(view):
        prev = session.app
        session.app = App(view, title=prev.title, size=prev.size, theme=prev.theme)
        return session.app, False
    raise LiveError(
        f"{block.where}: el bloque vivo no dibuja nada: termina en `App(...).run()`, en una "
        "expresión que dé un elemento o, con `continue`, define `view`"
    )


@contextmanager
def _as_main(module: types.ModuleType, script: str | None) -> Generator[None]:
    """Ejecuta como script principal: `__main__`, `sys.argv` y `sys.path` como `python script.py`."""
    saved_main, saved_argv, saved_path = sys.modules.get("__main__"), sys.argv, list(sys.path)
    sys.modules["__main__"] = module
    sys.argv = [script or module.__file__ or ""]
    if script:
        sys.path.insert(0, str(Path(script).parent))
    try:
        yield
    finally:
        if saved_main is not None:
            sys.modules["__main__"] = saved_main
        sys.argv = saved_argv
        sys.path[:] = saved_path


def _fragment(block: Block, items: list[Element]) -> App:
    align = block.attrs.get("align", "start")
    content = items[0] if len(items) == 1 else row(gap=12, align="center", wrap=True)[items]
    width = int(_size(block)[0] or FRAGMENT_WIDTH)

    # Sin `stretch`, la captura se ajusta también al ancho del contenido (hasta `width`).
    def view() -> Element:
        return column(align="stretch" if align == "stretch" else "start")[
            column(key=LIVE_KEY, padding=FRAGMENT_PADDING, align=align)[content]
        ]

    return App(view, size=(width, 2000))


def _size(block: Block) -> tuple[float | None, float | None]:
    m = _SIZE.match(block.attrs.get("size", ""))
    if not m:
        return None, None
    return float(m[1]), float(m[2]) if m[2] else None


def _render(block: Block, app: App, fragment: bool, out_dir: Path, index: int) -> list[Shot]:
    w, h = _size(block)
    size = (w or app.size[0], h or app.size[1])
    # Con el tema por defecto, una captura por tema; con uno propio (o un Signal), la suya.
    themes = [("light", DAYLIGHT), ("dark", MIDNIGHT)] if app.theme is MIDNIGHT else [("", app.theme)]
    forced = block.attrs.get("theme")
    if forced is not None:
        themes = [("", DAYLIGHT if forced == "light" else MIDNIGHT)]
    digest = hashlib.sha1(f"{block.code}\0{sorted(block.attrs.items())}".encode()).hexdigest()[:8]
    stem = posixpath.splitext(block.page)[0].replace("/", "-")
    shots = []
    saved = app.theme
    try:
        for name, theme in themes:
            app.theme = theme
            uri = f"_live/{stem}-{index + 1}-{digest}{'-' + name if name else ''}.png"
            path = out_dir / uri
            path.parent.mkdir(parents=True, exist_ok=True)
            _shoot(app, size, fragment, path)
            shots.append(Shot(uri, path, name))
    finally:
        app.theme = saved
    return shots


def _shoot(app: App, size: tuple[float, float], fragment: bool, path: Path) -> None:
    pilot = app.pilot(size=size, scale=SCALE)
    pilot.settle()
    if fragment:
        rect = pilot.rect(LIVE_KEY)
        if rect is None:
            raise LiveError("el fragmento no se pintó")
        x, y, w, h = rect
        pilot.resize(math.ceil(x + w), math.ceil(y + h))
        pilot.settle()
    pilot.png(os.fspath(path))
