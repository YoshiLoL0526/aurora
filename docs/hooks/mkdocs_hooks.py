"""Conecta los ejemplos vivos (`livedocs.py`) con MkDocs.

Antes de leer las páginas se ejecutan sus bloques vivos: las capturas se añaden al sitio como
archivos generados (así MkDocs valida los enlaces a ellas) y cada página recibe su Markdown con
las imágenes ya insertadas. Los enlaces a archivos del repositorio fuera de `docs/`
(`../examples/hello.py`) se convierten en enlaces a GitHub.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from mkdocs.structure.files import File, Files
from mkdocs.structure.pages import Page
from mkdocs.utils.meta import get_data

sys.path.insert(0, str(Path(__file__).resolve().parent))
import livedocs

OUT = livedocs.ROOT / "build" / "docs-live"
_OUTSIDE = re.compile(r"\]\(\.\./([^)#\s]+)(#[^)\s]*)?\)")
_pages: dict[str, str] = {}


def on_files(files: Files, *, config: MkDocsConfig) -> Files:
    _pages.clear()
    shutil.rmtree(OUT, ignore_errors=True)
    for page in list(files.documentation_pages()):
        if page.abs_src_path is None:
            continue
        text = Path(page.abs_src_path).read_text(encoding="utf-8")
        try:
            markdown, shots = livedocs.render_page(text, page.src_uri, OUT)
        except livedocs.LiveError as e:
            raise PluginError(str(e)) from e
        if shots:
            _pages[page.src_uri] = markdown
        for shot in shots:
            files.append(File.generated(config, shot.uri, abs_src_path=str(shot.path)))
    return files


def on_page_markdown(markdown: str, *, page: Page, config: MkDocsConfig, files: Files) -> str:
    if page.file.src_uri in _pages:
        markdown, _ = get_data(_pages[page.file.src_uri])  # sin el front matter, como llega aquí
    repo = (config.repo_url or "").rstrip("/")
    if not repo:
        return markdown
    return _OUTSIDE.sub(lambda m: f"]({repo}/blob/main/{m[1]}{m[2] or ''})", markdown)
