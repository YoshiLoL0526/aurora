"""La documentación empaquetada que imprime `aurora docs`, pensada para modelos de lenguaje.

`_docs/` guarda la chuleta (`llms.md`), la guía, las recetas y la referencia en Markdown limpio:
los mismos textos que publica el sitio, generados desde `docs/` por `docs/hooks/llmstxt.py` y
comprobados por `tests/test_llms.py`. Viajan en el wheel, así que un agente lee la documentación
de la versión instalada, no la de la web ni la que recuerde de su entrenamiento.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

DIR = Path(__file__).with_name("_docs")
PAGES = ("llms.md", "guide.md", "recipes.md", "reference.md")
"""Las páginas empaquetadas, en el orden de `aurora docs --full` (y de `llms-full.txt`)."""

# Dónde se buscan los temas de `aurora docs <tema>`: la referencia gana a la guía.
_TOPIC_ORDER = ("reference.md", "llms.md", "guide.md", "recipes.md")
_ALIASES = {
    "style": "propiedades-de-estilo",
    "estilo": "propiedades-de-estilo",
    "props": "propiedades-de-estilo",
    "tokens": "temas-y-tokens",
    "tema": "temas-y-tokens",
    "theme": "temas-y-tokens",
    "build": "empaquetado-aurora-build",
    "test": "pilot",
    "tests": "pilot",
    "reactividad": "reconstruccion-parcial",
}
# Las primitivas sin sección propia se explican juntas (y `column` no es la clase `Column`).
_PRIMITIVES = ("box", "column", "row", "text", "spacer")
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")


@dataclass(frozen=True)
class Section:
    """Una sección de una página: su encabezado y lo que hay hasta el siguiente del mismo nivel."""

    page: str
    level: int
    title: str
    path: tuple[str, ...]  # títulos de los encabezados que la contienen, con el suyo
    text: str  # la sección entera, con sus subsecciones
    own: str  # solo hasta el siguiente encabezado, de cualquier nivel


def read(page: str) -> str:
    return (DIR / page).read_text(encoding="utf-8")


def cheatsheet(version: str) -> str:
    """La chuleta, con la versión instalada bajo el título."""
    title, _, rest = read("llms.md").partition("\n")
    return f"{title}\n\nVersión instalada: Aurora {version}.\n{rest}"


def join(pages: list[tuple[str, str]], version: str) -> str:
    """Todas las páginas en un solo Markdown: `aurora docs --full` y `llms-full.txt`."""
    head = (
        f"# Aurora {version}: documentación completa\n\n"
        "> Chuleta, guía, recetas y referencia de Aurora (`aurora-ui`), una librería de UI de "
        "escritorio declarativa y reactiva en Python con núcleo nativo en Rust.\n"
    )
    body = "\n\n---\n\n".join(text.strip("\n") + "\n" for _, text in pages)
    return f"{head}\n---\n\n{body}"


def full(version: str) -> str:
    return join([(page, read(page)) for page in PAGES], version)


def normalize(text: str) -> str:
    """Para comparar temas: minúsculas, sin tildes ni signos, palabras unidas por guiones."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9_]+", "-", text).strip("-")


def parse(page: str, markdown: str) -> list[Section]:
    """Las secciones de una página, en orden (los `#` dentro de bloques de código no cuentan)."""
    lines = markdown.splitlines()
    heads: list[tuple[int, int, str]] = []  # (línea, nivel, título)
    fence: str | None = None
    for i, line in enumerate(lines):
        m = _FENCE.match(line)
        if m and (fence is None or m[1][0] == fence[0]):
            fence = None if fence else m[1]
            continue
        h = None if fence else _HEADING.match(line)
        if h:
            heads.append((i, len(h[1]), h[2]))
    sections = []
    stack: list[tuple[int, str]] = []
    for n, (start, level, title) in enumerate(heads):
        end = next((s for s, lv, _ in heads[n + 1 :] if lv <= level), len(lines))
        own_end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        sections.append(
            Section(
                page,
                level,
                title,
                tuple(t for _, t in stack),
                "\n".join(lines[start:end]).strip("\n") + "\n",
                "\n".join(lines[start:own_end]).strip("\n") + "\n",
            )
        )
    return sections


@cache
def sections() -> tuple[Section, ...]:
    return tuple(s for page in PAGES for s in parse(page, read(page)))


def keys(section: Section) -> list[str]:
    """Los nombres con los que se pide una sección (`button`, `pilot`, `temas-y-tokens`…), del más
    claro al menos: el que sale en `--list` y en `--search` es el primero que no se repite."""
    title = section.title
    found = re.findall(r"`@?(\w+)\(", title)  # `button(label, ...)`, `checkbox(...)` y `switch(...)`
    alone = re.fullmatch(r"`(\w+)`", title)  # `DragEvent`
    if alone:
        found.append(alone[1])
    first = re.match(r"[A-Za-z_]\w*", title) if section.level == 2 else None
    one_word = first is not None and not re.sub(r"\(.*?\)", "", title[first.end() :]).strip()
    if first and one_word:  # `## Pilot (tests de interacción)`
        found.append(first[0])
    found.append(title)
    if first and not one_word:  # `## Hot reload`: también `hot`, pero después de `hot-reload`
        found.append(first[0])
    return list(dict.fromkeys(normalize(k) for k in found if normalize(k)))


@cache
def topics() -> dict[str, Section]:
    """Cada nombre de tema y su sección; si se repite, gana la referencia y el primero."""
    index: dict[str, Section] = {}
    by_page = {page: [s for s in sections() if s.page == page] for page in PAGES}
    for page in _TOPIC_ORDER:
        for section in by_page[page]:
            if section.level == 1:
                continue
            for key in keys(section):
                index.setdefault(key, section)
    for alias, target in _ALIASES.items():
        if target in index:
            index.setdefault(alias, index[target])
    if "primitivas" in index:
        index.update(dict.fromkeys(_PRIMITIVES, index["primitivas"]))
    return index


def find(name: str) -> Section | None:
    """La sección de un tema; si no hay uno exacto, la única cuyos nombres contienen esa palabra
    (`kanban` → `tablero-kanban`)."""
    key = normalize(name.removesuffix("()"))
    if key in topics():
        return topics()[key]
    found = {id(s): s for k, s in topics().items() if key in k.split("-") and not s.title.startswith("`")}
    return next(iter(found.values())) if len(found) == 1 else None


def suggest(name: str, n: int = 3) -> list[str]:
    import difflib  # solo al fallar

    return difflib.get_close_matches(normalize(name), list(topics()), n=n, cutoff=0.6)


def command(section: Section) -> str:
    """El `aurora docs …` que lleva a la sección (o con el título, si ningún nombre es suyo)."""
    index = topics()
    name = next((k for k in keys(section) if index.get(k) == section), None)
    return f"aurora docs {name}" if name else f'aurora docs "{section.title}"'


def search(query: str, limit: int = 40) -> list[tuple[Section, str]]:
    """Las secciones cuyo texto propio contiene `query` (sin distinguir tildes ni mayúsculas),
    primero las que lo tienen en el título, con la primera línea donde aparece."""
    needle = _fold(query)
    hits: list[tuple[int, Section, str]] = []
    for section in sections():
        if section.level == 1 and section.page != "llms.md":
            continue
        in_title = needle in _fold(section.title)
        line = next((ln.strip() for ln in section.own.splitlines()[1:] if needle in _fold(ln)), "")
        if in_title or line:
            hits.append((0 if in_title else 1, section, line))
    hits.sort(key=lambda h: h[0])
    return [(s, line) for _, s, line in hits[:limit]]


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


def page_title(page: str) -> str:
    first = read(page).partition("\n")[0]
    return first.lstrip("# ").strip()
