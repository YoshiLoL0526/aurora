"""Texto enriquecido: tramos con estilo propio dentro de un párrafo (`rich_text`)
y un render de Markdown básico construido sobre ellos (`markdown`).

Un párrafo enriquecido es un único nodo de texto: el núcleo lo «shapea» y lo
parte en líneas entero, así que los cambios de peso, color o fuente no rompen
el ajuste de línea ni el kerning entre tramos. Python solo describe los tramos.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from typing import Any

from .elements import Element, box, column, row, text

# Familias monoespaciadas para el código, en orden de preferencia (la primera instalada gana).
MONO = "Cascadia Mono, Consolas, SF Mono, Menlo, DejaVu Sans Mono, Liberation Mono, monospace"


@dataclass(frozen=True, slots=True)
class Span:
    """Tramo de un `rich_text`: un trozo de texto con su estilo. Créalo con `span()`."""

    content: str
    weight: int | None = None
    color: str | None = None
    italic: bool = False
    underline: bool = False
    strike: bool = False
    code: bool = False
    size: float | None = None
    family: str | None = None
    bg: str | None = None
    on_click: Callable[[], Any] | None = None


def span(
    content: str,
    *,
    weight: int | None = None,
    color: str | None = None,
    italic: bool = False,
    underline: bool = False,
    strike: bool = False,
    code: bool = False,
    size: float | None = None,
    family: str | None = None,
    bg: str | None = None,
    on_click: Callable[[], Any] | None = None,
) -> Span:
    """Tramo con estilo propio para `rich_text`. Lo que no se fija se hereda del párrafo.

    `code` lo escribe en monoespaciada sobre un fondo suave (`$surface_hover`);
    `on_click` lo convierte en un enlace (en `$primary` y subrayado, salvo que
    se fije otro `color` o `underline`).
    """
    return Span(content, weight, color, italic, underline, strike, code, size, family, bg, on_click)


Spans = Span | str | Iterable["Spans"] | None


def _flatten(parts: Spans) -> Iterable[Span]:
    if parts is None or parts == "":
        return
    if isinstance(parts, Span):
        if parts.content:
            yield parts
    elif isinstance(parts, str):
        yield Span(parts)
    else:
        for part in parts:
            yield from _flatten(part)


def rich_text(*parts: Spans, key: str | None = None, **style: Any) -> Element:
    """Párrafo con tramos de estilos distintos: `rich_text("Pulsa ", span("Guardar", weight=700), ".")`.

    Cada parte es un texto (con el estilo del párrafo), un `span(...)` o una
    lista de ellos. Todo forma un único párrafo: se parte en líneas por donde
    toque, aunque sea en mitad de un tramo, y los tramos con `on_click` son
    enlaces que reciben clics (con cursor de mano) y se anuncian como `"link"`
    a los lectores de pantalla. Los `estilo` son los de `text` (`size`,
    `color`, `max_lines`, `text_align`…) y valen para los tramos que no los fijan.
    """
    spans = list(_flatten(parts))
    links: list[Callable[[], Any]] = []
    described: list[tuple[Any, ...]] = []
    for s in spans:
        link = None
        if s.on_click is not None:
            link = len(links)
            links.append(s.on_click)
        is_link = link is not None
        described.append(
            (
                len(s.content),
                s.color or ("$primary" if is_link else None),
                s.bg or ("$surface_hover" if s.code else None),
                s.weight,
                s.size,
                s.family or (MONO if s.code else None),
                s.italic,
                s.underline or (is_link and s.color is None),
                s.strike,
                link,
            )
        )
    handlers: dict[str, Any] = {"on_link": (lambda i: links[i]())} if links else {}
    return Element(
        "text",
        content="".join(s.content for s in spans),
        key=key,
        spans=tuple(described),
        **handlers,
        **style,
    )


# --- Markdown -----------------------------------------------------------------------

# Escapes de Markdown: el carácter se protege (en el área de uso privado) y se
# restaura al final, para que no abra énfasis ni enlaces.
_ESCAPABLE = "\\`*_{}[]()#+-.!~>|"
_ESCAPE = re.compile(r"\\([" + re.escape(_ESCAPABLE) + r"])")
_PROTECTED = {chr(0xE000 + i): c for i, c in enumerate(_ESCAPABLE)}
_PROTECT = {c: p for p, c in _PROTECTED.items()}

_INLINE = re.compile(
    r"`(?P<code>[^`]+)`"
    r"|\[(?P<label>[^\]]+)\]\((?P<url>[^)\s]+)\)"
    r"|\*\*(?P<bold>.+?)\*\*"
    r"|(?<![\w])__(?P<bold2>.+?)__(?![\w])"
    r"|~~(?P<strike>.+?)~~"
    r"|\*(?P<em>[^*\s](?:.*?[^*\s])?)\*"
    r"|(?<![\w])_(?P<em2>[^_\s](?:.*?[^_\s])?)_(?![\w])"
)


def _restore(s: str) -> str:
    return "".join(_PROTECTED.get(c, c) for c in s)


_PLAIN = Span("")


def _inline(source: str, on_link: Callable[[str], Any], base: Span = _PLAIN) -> list[Span]:
    """Tramos de un texto con formato en línea (énfasis, código, enlaces, tachado)."""
    out: list[Span] = []
    at = 0
    for m in _INLINE.finditer(source):
        if m.start() > at:
            out.append(replace(base, content=_restore(source[at : m.start()])))
        at = m.end()
        if m["code"] is not None:
            out.append(replace(base, content=_restore(m["code"]), code=True))
        elif m["label"] is not None:
            url = _restore(m["url"])
            inner = _inline(m["label"], on_link, base)
            out.extend(replace(s, on_click=lambda url=url: on_link(url)) for s in inner)
        elif m["bold"] is not None or m["bold2"] is not None:
            out.extend(_inline(m["bold"] or m["bold2"], on_link, replace(base, weight=700)))
        elif m["strike"] is not None:
            out.extend(_inline(m["strike"], on_link, replace(base, strike=True)))
        else:
            out.extend(_inline(m["em"] or m["em2"], on_link, replace(base, italic=True)))
    if at < len(source):
        out.append(replace(base, content=_restore(source[at:])))
    return out


def _open_url(url: str) -> None:
    """Destino por defecto de los enlaces de `markdown`: el navegador del sistema."""
    if url.startswith(("http://", "https://", "mailto:")):
        import webbrowser  # se carga al usarse: importarlo alarga el arranque

        webbrowser.open(url)


_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_BULLET = re.compile(r"^(\s*)([-*+])\s+(.*)$")
_NUMBERED = re.compile(r"^(\s*)(\d{1,9})[.)]\s+(.*)$")
_FENCE = re.compile(r"^\s*(```|~~~)\s*([\w+-]*)\s*$")
_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_HEADING_SIZES = (26, 21, 18, 16, 14, 13)


def markdown(
    source: str,
    *,
    on_link: Callable[[str], Any] | None = None,
    gap: float = 12,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Render de Markdown básico: títulos, párrafos, listas (con viñetas, numeradas
    y anidadas), citas, código en línea y en bloque, separadores, énfasis
    (`*cursiva*`, `**negrita**`, `~~tachado~~`) y enlaces.

    Devuelve una columna (los `estilo` van a ella; `gap` separa los bloques).
    Cada párrafo es un `rich_text`, así que se parte en líneas con el ancho
    disponible. Los enlaces llaman a `on_link(url)`; sin él, los `http(s)` y
    `mailto:` se abren en el navegador. Los títulos son `"heading"` con su
    nivel para los lectores de pantalla y las listas, `"list"` de
    `"listitem"`s. No admite tablas, imágenes ni HTML: su texto se muestra tal cual.
    """
    follow = on_link or _open_url
    lines = _ESCAPE.sub(lambda m: _PROTECT[m[1]], source.expandtabs(4)).splitlines()
    return column(**{"gap": gap, "key": key, **style})[_blocks(lines, follow)]


def _blocks(lines: list[str], on_link: Callable[[str], Any]) -> list[Element]:
    out: list[Element] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if fence := _FENCE.match(line):
            body: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence[1]):
                body.append(_restore(lines[i]))
                i += 1
            i += 1  # la valla de cierre
            out.append(_code_block("\n".join(body)))
            continue
        if heading := _HEADING.match(line):
            level = len(heading[1])
            out.append(
                rich_text(
                    _inline(heading[2], on_link),
                    size=_HEADING_SIZES[level - 1],
                    weight=700 if level <= 3 else 600,
                    role="heading",
                    level=level,
                    padding=(4 if level <= 2 else 0, 0, 0, 0),
                )
            )
            i += 1
            continue
        if _RULE.match(line):
            out.append(box(height=1, bg="$border"))
            i += 1
            continue
        if _QUOTE.match(line):
            quoted: list[str] = []
            while i < len(lines) and (m := _QUOTE.match(lines[i])):
                quoted.append(m[1])
                i += 1
            out.append(
                row(gap=12)[
                    box(width=3, radius=2, bg="$border", shrink=0),
                    column(gap=8, grow=1, width=0, color="$muted")[_blocks(quoted, on_link)],
                ]
            )
            continue
        if _BULLET.match(line) or _NUMBERED.match(line):
            items: list[tuple[int, str | None, str]] = []
            while i < len(lines):
                m = _BULLET.match(lines[i]) or _NUMBERED.match(lines[i])
                if m:
                    marker = None if m.re is _BULLET else m[2]
                    items.append((len(m[1]), marker, m[3]))
                elif lines[i].strip() and items and lines[i].startswith(" "):
                    # Continuación del último elemento.
                    indent, marker, body_text = items[-1]
                    items[-1] = (indent, marker, f"{body_text} {lines[i].strip()}")
                else:
                    break
                i += 1
            out.append(_list(items, on_link))
            continue
        # Párrafo: líneas seguidas hasta una en blanco o el inicio de otro bloque.
        para: list[str] = []
        while i < len(lines) and lines[i].strip() and not _starts_block(lines[i]):
            para.append(lines[i].strip())
            i += 1
        out.append(rich_text(_inline(" ".join(para), on_link), line_height=1.5))
    return out


def _starts_block(line: str) -> bool:
    return any(p.match(line) for p in (_FENCE, _HEADING, _RULE, _QUOTE, _BULLET, _NUMBERED))


def _list(items: list[tuple[int, str | None, str]], on_link: Callable[[str], Any]) -> Element:
    """Lista con anidamiento por sangría: cada nivel, una lista dentro del elemento anterior."""
    base = items[0][0]
    rows: list[Element] = []
    j = 0
    while j < len(items):
        indent, marker, body_text = items[j]
        nested: list[tuple[int, str | None, str]] = []
        j += 1
        while j < len(items) and items[j][0] > indent:
            nested.append(items[j])
            j += 1
        bullet = f"{marker}." if marker is not None else "•"
        content = column(gap=6, grow=1, width=0)[
            rich_text(_inline(body_text, on_link), line_height=1.5),
            _list(nested, on_link) if nested else None,
        ]
        rows.append(
            row(gap=8, role="listitem", padding=(0, 0, 0, max(0, indent - base)))[
                text(bullet, color="$muted", min_width=14, line_height=1.5, hidden=True), content
            ]
        )
    return column(gap=6, role="list")[rows]


def _code_block(source: str) -> Element:
    return box(
        padding=(10, 14),
        radius="$sm",
        bg="$surface",
        border_width=1,
        border_color="$border",
    )[text(source, family=MONO, size=13, line_height=1.45)]
