"""Ejemplos vivos de la documentación: todos se ejecutan y renderizan, y el formato se respeta."""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docs" / "hooks"))
import livedocs

PAGES = sorted(p.name for p in livedocs.DOCS.glob("*.md") if "python live" in p.read_text(encoding="utf-8"))


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_hay_paginas_con_ejemplos_vivos():
    assert {"index.md", "guide.md", "reference.md", "examples.md"} <= set(PAGES)


@pytest.mark.parametrize("page", PAGES)
def test_los_ejemplos_vivos_de_la_pagina_funcionan(page: str, tmp_path: Path):
    text = (livedocs.DOCS / page).read_text(encoding="utf-8")
    markdown, shots = livedocs.render_page(text, page, tmp_path)
    assert shots
    assert "python live" not in markdown
    assert livedocs.HIDDEN not in markdown
    for shot in shots:
        assert shot.path.is_file()
        assert shot.uri in markdown
        w, h = _png_size(shot.path)
        assert w > 0 and h > 0


def _render(markdown: str, tmp_path: Path) -> tuple[str, list[livedocs.Shot]]:
    return livedocs.render_page(markdown, "pagina.md", tmp_path)


def test_app_en_claro_y_oscuro_y_lineas_ocultas(tmp_path: Path):
    markdown, shots = _render(
        """# Título

```python live size=300x120
from aurora import App, Signal, text

n = Signal(0)
n.set(7)  # oculto
App(lambda: text(lambda: f"n = {n()}"), size=(800, 600)).run()
```

Fin.
""",
        tmp_path,
    )
    assert [s.theme for s in shots] == ["light", "dark"]
    assert all(_png_size(s.path) == (600, 240) for s in shots)  # size= sustituye al de la App, ×2
    assert "n.set(7)" not in markdown
    assert "```python\nfrom aurora import App" in markdown
    assert "#only-light){ .live" in markdown and "#only-dark){ .live" in markdown
    assert markdown.endswith("Fin.\n")


def test_region_oculta_sin_huecos(tmp_path: Path):
    markdown, _ = _render(
        """```python live
# oculto: inicio
from aurora import text

datos = (
    "uno",
    "dos",
)
# oculto: fin
etiqueta = "x"

valor = 1  # oculto


text(etiqueta)
```
""",
        tmp_path,
    )
    assert '```python\netiqueta = "x"\n\n\ntext(etiqueta)\n```' in markdown


def test_fragmento_se_ajusta_al_contenido(tmp_path: Path):
    _, shots = _render(
        """```python live
from aurora import box
box(width=100, height=40, bg="$primary")
```
""",
        tmp_path,
    )
    pad = livedocs.FRAGMENT_PADDING
    assert _png_size(shots[0].path) == ((100 + 2 * pad) * 2, (40 + 2 * pad) * 2)


def test_fragmento_con_lista_y_stretch(tmp_path: Path):
    _, shots = _render(
        """```python live align=stretch size=400 theme=dark
from aurora import box
[box(width=50, height=20), box(width=50, height=20)]
```
""",
        tmp_path,
    )
    assert len(shots) == 1 and shots[0].theme == ""
    assert _png_size(shots[0].path)[0] == 800


def test_continue_comparte_el_espacio_de_nombres(tmp_path: Path):
    _, shots = _render(
        """```python live
from aurora import App, text

def view():
    return text("uno")

App(view, size=(320, 100)).run()
```

```python live continue
def view():
    return text("dos")
```
""",
        tmp_path,
    )
    assert len(shots) == 4
    assert _png_size(shots[-1].path) == (640, 200)  # la app anterior, con la vista nueva


def test_tema_propio_una_sola_captura(tmp_path: Path):
    _, shots = _render(
        """```python live
from aurora import DAYLIGHT, App, text
App(lambda: text("hola"), size=(200, 80), theme=DAYLIGHT).run()
```
""",
        tmp_path,
    )
    assert [s.theme for s in shots] == [""]


def test_errores_con_pagina_y_linea(tmp_path: Path):
    with pytest.raises(
        livedocs.LiveError, match=r"pagina\.md:3: el ejemplo vivo falló(.|\n)*ZeroDivisionError"
    ):
        _render("Texto\n\n```python live\n1 / 0\n```\n", tmp_path)
    with pytest.raises(livedocs.LiveError, match=r"pagina\.md:1: el bloque vivo no dibuja nada"):
        _render("```python live\nx = 1\n```\n", tmp_path)
    with pytest.raises(livedocs.LiveError, match="atributo desconocido 'tamaño'"):
        _render("```python live tamaño=3\n```\n", tmp_path)
    with pytest.raises(livedocs.LiveError, match="size='grande'"):
        _render("```python live size=grande\n```\n", tmp_path)
    with pytest.raises(livedocs.LiveError, match="necesita su"):
        _render("```python live\n# oculto: inicio\nx = 1\n```\n", tmp_path)
    with pytest.raises(livedocs.LiveError, match="sin cerrar"):
        _render("```python live\nx = 1\n", tmp_path)


def test_bloque_sangrado_y_codigo_normal_intacto(tmp_path: Path):
    source = """- Paso:

    ```python live
    from aurora import text
    text("hola")
    ```

```python
no_se_ejecuta()
```
"""
    markdown, shots = _render(source, tmp_path)
    assert len(shots) == 2
    assert '    ```python\n    from aurora import text\n    text("hola")\n    ```' in markdown
    assert "```python\nno_se_ejecuta()\n```" in markdown
