"""Documentación para modelos de lenguaje: `llms.txt`, `llms-full.txt` y la chuleta.

Los modelos no conocen Aurora por su entrenamiento: todo lo que sepan sale de lo que se les da,
y tiene que corresponder a la versión instalada. Este módulo convierte las páginas de `docs/` en
Markdown limpio para ellos (sin el HTML de la portada, con los bloques vivos como código normal
y sin sus líneas `# oculto`) y genera las partes mecánicas de la chuleta (`docs/llms.md`): las
firmas, las props de estilo y los tokens salen de la propia librería, no se escriben a mano.

Lo usan `mkdocs_hooks.py` (publica `llms.txt`, `llms-full.txt` y cada página como `.md`) y
`tests/test_llms.py`, que regenera la chuleta y la copia empaquetada en `python/aurora/_docs/`
(la que imprime `aurora docs`) y falla si alguna se ha quedado atrás. Como `livedocs.py`, no
depende de MkDocs.
"""

from __future__ import annotations

import inspect
import re
import sys
import typing
from collections.abc import Callable, Iterable
from pathlib import Path
from types import ModuleType, UnionType

import livedocs

import aurora
from aurora import MIDNIGHT, _llmdocs, _style, animate, dialogs, menus

ROOT = livedocs.ROOT
DOCS = livedocs.DOCS
BUNDLE = ROOT / "python" / "aurora" / "_docs"
"""La copia empaquetada: viaja en el wheel y es lo que lee `aurora docs`."""
CHEATSHEET = DOCS / "llms.md"
REPO = "https://github.com/YoshiLoL0526/aurora"

_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_ATTR_LIST = re.compile(r"[ \t]*\{:?[ \t]*[.#][^}\n]*\}")
_OUTSIDE = re.compile(r"\]\(\.\./([^)#\s]+)(#[^)\s]*)?\)")
_SNIPPET = re.compile(r'^--8<--[ \t]+"([^"]+)"[ \t]*$')
_ADMONITION = re.compile(r'^(!!!|\?\?\?\+?)[ \t]+\w+(?:[ \t]+"([^"]*)")?[ \t]*$')
_HTML_LINE = re.compile(r"^[ \t]*</?[a-zA-Z][^>]*>[ \t]*$")
_IMAGE_LINE = re.compile(r"^[ \t]*!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?[ \t]*$")
_COMMENT_LINE = re.compile(r"^[ \t]*<!--.*-->[ \t]*$")
_INLINE_HTML = re.compile(r"^[ \t]*<([a-z]+)\b[^>]*>(.*?)</\1>[ \t]*$")  # `<p class="x">texto</p>`


# --- Markdown limpio --------------------------------------------------------------------------


def clean(text: str, page: str, *, repo: str = REPO) -> str:
    """El Markdown de `page` tal como lo lee un modelo.

    Sin front matter, sin el HTML ni las imágenes de la portada, sin listas de atributos
    (`{ .md-button }`, `{ #ancla }`) ni comentarios HTML; los bloques vivos quedan como
    ```` ```python ```` con solo el código que se muestra; las advertencias (`!!! tip`), como citas;
    los `--8<--` se sustituyen por el archivo incluido y los enlaces fuera de `docs/`, por enlaces
    a GitHub.
    """
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = _live_as_code(text, page, repo)
    out: list[str] = []
    fence: str | None = None
    admonition = False

    def emit(line: str) -> None:
        # Fuera del código, nunca dos líneas vacías seguidas (lo que se quita deja huecos).
        if fence is None and not line.strip() and (not out or not out[-1].strip()):
            return
        out.append(line)

    for line in text.splitlines():
        m = _FENCE.match(line)
        if fence is not None:
            out.append(_quote(line) if admonition else line)
            if m and m[1][0] == fence[0] and len(m[1]) >= len(fence) and not line.strip()[len(m[1]) :]:
                fence = None
            continue
        if admonition and (line.startswith("    ") or not line.strip()):
            out.append(_quote(line))
            if m:
                fence = m[1]
            continue
        if admonition:
            admonition = False
            while out and out[-1] == ">":  # la cita se cierra con una línea vacía
                out.pop()
            emit("")
        if m:
            fence = m[1]
            out.append(line)
            continue
        snippet = _SNIPPET.match(line)
        if snippet:
            out.append(clean((ROOT / snippet[1]).read_text(encoding="utf-8"), snippet[1], repo=repo))
            continue
        head = _ADMONITION.match(line)
        if head:
            admonition = True
            if head[2]:
                out.append(f"> **{head[2]}**")
            continue
        if _HTML_LINE.match(line) or _IMAGE_LINE.match(line) or _COMMENT_LINE.match(line):
            continue
        line = _INLINE_HTML.sub(r"\2", line)
        line = _ATTR_LIST.sub("", line)
        line = _OUTSIDE.sub(lambda g: f"]({repo}/blob/main/{g[1]}{g[2] or ''})", line)
        emit(line)
    while out and out[-1] == ">":
        out.pop()
    return "\n".join(out).strip("\n") + "\n"


def _quote(line: str) -> str:
    body = line[4:] if line.startswith("    ") else line.strip()
    return f"> {body}".rstrip()


def _live_as_code(text: str, page: str, repo: str) -> str:
    """Cada bloque vivo como un bloque `python` normal, con solo lo que se muestra.

    Un bloque con `file=` (la galería) se convierte en un enlace al ejemplo."""
    blocks = livedocs.find_blocks(text, page)
    if not blocks:
        return text
    lines = text.splitlines()
    out: list[str] = []
    prev = 0
    for block in blocks:
        out.extend(lines[prev : block.start])
        file = block.attrs.get("file")
        if file:
            alt = block.attrs.get("alt", "captura")
            out.append(f"{block.indent}Captura de [`{file}`]({repo}/blob/main/{file}): {alt}.")
        else:
            out.append(f"{block.indent}{block.fence}python")
            out.extend(f"{block.indent}{ln}" if ln else "" for ln in block.shown.splitlines())
            out.append(f"{block.indent}{block.fence}")
        prev = block.end + 1
    out.extend(lines[prev:])
    return "\n".join(out) + "\n"


def bundle() -> dict[str, str]:
    """Las páginas que viajan en el paquete (`aurora._llmdocs.PAGES`), ya limpias."""
    return {name: clean((DOCS / name).read_text(encoding="utf-8"), name) for name in _llmdocs.PAGES}


# --- llms.txt ---------------------------------------------------------------------------------


def summary(markdown: str) -> str:
    """La primera frase del primer párrafo de texto de una página limpia (para `llms.txt`)."""
    fence = False
    paragraph: list[str] = []
    for line in markdown.splitlines():
        if _FENCE.match(line):
            fence = not fence
            continue
        if fence:
            continue
        stripped = line.strip()
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith(("#", ">", "|", "-", "*", "[", "!")) and not paragraph:
            continue
        paragraph.append(stripped)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", " ".join(paragraph))
    sentence = re.split(r"(?<=[.:])\s", text, maxsplit=1)[0]
    return sentence.rstrip(".:")


def llms_txt(pages: Iterable[tuple[str, str, str]], *, site_url: str, description: str) -> str:
    """`llms.txt` en el formato de llmstxt.org: título, resumen y un enlace por página.

    `pages` son `(título, página, markdown limpio)` en el orden de la navegación. La portada y las
    de `_llmdocs.PAGES` (la chuleta, la guía, las recetas y la referencia) van en *Docs*; el resto
    (arquitectura, estabilidad, cambios…), en *Optional*, que un modelo puede saltarse si va corto
    de contexto."""
    base = site_url.rstrip("/") + "/"
    docs: list[str] = []
    optional: list[str] = []
    for title, page, markdown in pages:
        entry = f"- [{title}]({base}{page}): {summary(markdown)}"
        (docs if page in (*_llmdocs.PAGES, "index.md") else optional).append(entry)
    docs.sort(key=lambda e: next((i for i, p in enumerate(_llmdocs.PAGES) if f"]({base}{p})" in e), 99))
    return "\n".join(
        [
            "# Aurora",
            "",
            f"> {description}",
            "",
            f"Versión {aurora.__version__} (`aurora-ui` en PyPI). Aurora es reciente: no está en los datos",
            "de entrenamiento de los modelos, así que usa solo la API de estos documentos. Empieza por la",
            "chuleta. Con Aurora instalado, `aurora docs` imprime la documentación de la versión instalada",
            "(`aurora docs <tema>`, `aurora docs --search <texto>`, `aurora docs --full`).",
            f"Todo junto, en un solo archivo: {base}llms-full.txt",
            "",
            "## Docs",
            "",
            *docs,
            "",
            "## Optional",
            "",
            *optional,
            "",
        ]
    )


def write_site(
    site_dir: Path,
    nav: Iterable[tuple[str, str]],
    *,
    site_url: str,
    description: str,
    repo: str = REPO,
) -> list[Path]:
    """Escribe en el sitio cada página de `nav` (`(título, página)`) como Markdown limpio junto a
    su HTML, `llms.txt` y `llms-full.txt`. Devuelve las rutas escritas."""
    written: list[Path] = []
    pages: list[tuple[str, str, str]] = []
    for title, page in nav:
        markdown = clean((DOCS / page).read_text(encoding="utf-8"), page, repo=repo)
        pages.append((title, page, markdown))
        written.append(site_dir / page)
        write_text(written[-1], markdown)
    by_page = {page: markdown for _, page, markdown in pages}
    full = _llmdocs.join([(p, by_page[p]) for p in _llmdocs.PAGES if p in by_page], aurora.__version__)
    for name, text in (
        ("llms.txt", llms_txt(pages, site_url=site_url, description=description)),
        ("llms-full.txt", full),
    ):
        written.append(site_dir / name)
        write_text(written[-1], text)
    return written


# --- Partes generadas de la chuleta -----------------------------------------------------------

_GENERATED = re.compile(r"(<!-- generado: (\w+) -->\n)(.*?)(<!-- /generado -->)", re.S)

# Grupos de la chuleta: el módulo donde se define cada nombre de `aurora.__all__`.
_GROUPS = [
    ("Primitivas", ("aurora.elements", "aurora.canvas", "aurora.charts", "aurora.richtext")),
    ("Componentes", ("aurora.components", "aurora.table")),
]
_CLASSES = ("App", "Window", "Signal", "Pilot", "Element", "Theme")


def _clean_annotation(text: str) -> str:
    text = re.sub(r"ForwardRef\('(\w+)'\)", r"\1", text).replace("NoneType", "None").replace("~", "")
    return re.sub(r"\b(?:collections\.abc|typing|types|os|datetime|aurora(?:\.\w+)*)\.", "", text)


def _aliases(objects: Iterable[object], text: str) -> list[str]:
    """Los alias de tipo que usan las firmas (`Variant`, `Options`…), con lo que significan."""
    found: dict[str, str] = {}
    for obj in objects:
        module = sys.modules.get(getattr(obj, "__module__", "") or "")
        for name in sorted(set(re.findall(r"\b([A-Z]\w+)\b", text))):
            value = getattr(module, name, None)
            if name not in found and (typing.get_origin(value) is not None or isinstance(value, UnionType)):
                found[name] = f"{name} = {_clean_annotation(repr(value))}"
    return [found[name] for name in sorted(found)]


def _default(value: object) -> str:
    if inspect.isclass(value):
        return value.__name__
    if inspect.isroutine(value):
        return "..."
    text = repr(value)
    if text.startswith("Theme("):
        return "MIDNIGHT"
    return "..." if len(text) > 32 else text


def signature(obj: Callable[..., object], *, skip_self: bool = False) -> str:
    """La firma compacta: tipos sin comillas, `**style` sin anotar, sin retorno ni defaults largos."""
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return "(...)"
    parts: list[str] = []
    star = False
    params = list(sig.parameters.values())
    if skip_self and params and params[0].name == "self":
        params = params[1:]
    for p in params:
        if p.kind is p.POSITIONAL_ONLY:
            text = p.name
        elif p.kind is p.VAR_KEYWORD:
            parts.append(f"**{p.name}")
            continue
        elif p.kind is p.VAR_POSITIONAL:
            star = True
            text = f"*{p.name}"
        else:
            if p.kind is p.KEYWORD_ONLY and not star:
                parts.append("*")
                star = True
            text = p.name
        if p.annotation is not p.empty:
            ann = p.annotation if isinstance(p.annotation, str) else inspect.formatannotation(p.annotation)
            text += f": {_clean_annotation(ann)}"
        if p.default is not p.empty:
            text += f" = {_default(p.default)}" if p.annotation is not p.empty else f"={_default(p.default)}"
        parts.append(text)
    return f"({', '.join(parts)})"


def _group(obj: object) -> str:
    module = getattr(obj, "__module__", "") or ""
    for title, prefixes in _GROUPS:
        if module.startswith(prefixes):
            return title
    return "Utilidades"


def _members(cls: type) -> list[str]:
    lines = []
    for name, member in sorted(vars(cls).items()):
        if name.startswith("_"):
            continue
        if isinstance(member, staticmethod | classmethod):
            lines.append(f"    .{name}{signature(member.__func__)}")
        elif callable(member) and not isinstance(member, type):
            lines.append(f"    .{name}{signature(member, skip_self=True)}")
        else:
            lines.append(f"    .{name}")
    return lines


def _module_functions(module: ModuleType) -> list[str]:
    prefix = module.__name__.removeprefix("aurora.")
    return [
        f"{prefix}.{name}{signature(getattr(module, name))}"
        for name in sorted(module.__all__)
        if inspect.isroutine(getattr(module, name))
    ]


def signatures() -> str:
    """Las firmas de las primitivas, los componentes, las clases principales y los módulos."""
    groups: dict[str, list[str]] = {"Primitivas": [], "Componentes": [], "Utilidades": []}
    functions = [getattr(aurora, name) for name in sorted(aurora.__all__)]
    functions = [obj for obj in functions if inspect.isroutine(obj)]
    for obj in functions:
        groups[_group(obj)].append(f"{obj.__name__}{signature(obj)}")
    out: list[str] = []
    for title, lines in groups.items():
        out += [f"### {title}", "", "```python", *lines, "```", ""]
    aliases = _aliases(functions, "\n".join(line for lines in groups.values() for line in lines))
    out += ["### Alias de tipos de las firmas", "", "```python", *aliases, "```", ""]
    out += ["### Clases", "", "```python"]
    for name in _CLASSES:
        cls = getattr(aurora, name)
        out.append(f"{name}{signature(cls)}")
        out.extend(_members(cls))
    out += ["```", "", "### Módulos `animate`, `dialogs` y `menus`", "", "```python"]
    for module in (animate, dialogs, menus):
        out.extend(_module_functions(module))
    out += ["```", ""]
    # Comillas dobles, como las deja Ruff (que formatea los bloques de Python del Markdown).
    return "\n".join(out).replace("'", '"')


def _style_type(annotation: str) -> str:
    """`Prop[Literal['row', 'column']]` → `'row' | 'column'` (toda prop admite además una función)."""
    text = re.sub(r"^Prop\[(.*)\]$", r"\1", annotation.strip())
    text = re.sub(r"Literal\[(.*?)\]", lambda m: " | ".join(s.strip() for s in m[1].split(",")), text)
    text = text.replace('"', "'").replace("os.PathLike[str]", "PathLike")
    aliases = {"Length": "float | 'NN%'", "Edges": "float | (v, h) | (t, r, b, l)"}
    if text in aliases:
        return aliases[text]
    literal = getattr(_style, text, None)  # `Align`, `Cursor`…
    if typing.get_origin(literal) is typing.Literal:
        return " | ".join(repr(v) for v in typing.get_args(literal))
    return re.sub(r"\bColor\b", "color", text)


def style_props() -> str:
    """Las claves de `aurora.Style`, agrupadas como en su definición, con sus valores.

    Se leen del código (no con `get_type_hints`) para conservar los alias (`Color`, `Edges`) y
    los comentarios que agrupan las claves."""
    source = inspect.getsource(_style.Style)
    out: list[str] = []
    group = ""
    rows: list[str] = []

    def flush() -> None:
        if group and rows:
            out.extend([f"- **{group}**: " + ", ".join(rows)])
        rows.clear()

    for line in source.splitlines()[1:]:
        stripped = line.strip()
        comment = re.match(r"^# (.+?)(?: \(.*\))?$", stripped)
        if comment:
            flush()
            group = comment[1]
            continue
        field = re.match(r"^(\w+): (.+)$", stripped)
        if not field or field[1] == "key":
            continue
        name, annotation = field[1], field[2]
        if name.startswith("on_"):
            rows.append(f"`{name}`")
        elif name in _style.ALIASES:
            rows.append(f"`{name}` (= `{_style.ALIASES[name]}`)")
        else:
            rows.append(f"`{name}`: {_style_type(annotation)}")
    flush()
    return "\n".join(out) + "\n"


def tokens() -> str:
    """Los tokens del tema por defecto: colores y radios."""
    colors = ", ".join(f"`${name}`" for name in MIDNIGHT.colors)
    radius = ", ".join(f"`${name}` ({value:g})" for name, value in MIDNIGHT.radius.items())
    return f"- **Colores**: {colors}\n- **Radios**: {radius}\n"


GENERATORS: dict[str, Callable[[], str]] = {
    "firmas": signatures,
    "estilo": style_props,
    "tokens": tokens,
}


def regenerate(text: str) -> str:
    """La chuleta con sus partes generadas (`<!-- generado: nombre -->`) al día."""

    def replace(m: re.Match[str]) -> str:
        name = m[2]
        if name not in GENERATORS:
            raise KeyError(f"docs/llms.md: parte generada desconocida {name!r} (hay: {sorted(GENERATORS)})")
        return f"{m[1]}\n{GENERATORS[name]().strip()}\n\n{m[4]}"

    return _GENERATED.sub(replace, text)


def generated_names(text: str) -> list[str]:
    return [m[2] for m in _GENERATED.finditer(text)]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
