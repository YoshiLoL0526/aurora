"""Documentación para modelos: la chuleta, la copia empaquetada, `llms.txt` y `aurora docs`.

La chuleta (`docs/llms.md`) tiene partes generadas desde la librería (firmas, props de estilo y
tokens) y `python/aurora/_docs/` guarda la versión limpia de las páginas que imprime
`aurora docs`. Si una se queda atrás, estos tests fallan. Para regenerarlas:

    AURORA_UPDATE_API=1 uv run pytest tests/test_llms.py
"""

from __future__ import annotations

import inspect
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docs" / "hooks"))
import llmstxt

import aurora
from aurora import _agents, _llmdocs, _style
from aurora.cli import main

UPDATE = bool(os.environ.get("AURORA_UPDATE_API"))
REGENERATE = "regenera con AURORA_UPDATE_API=1 uv run pytest tests/test_llms.py"


def _public_functions() -> list[str]:
    return [n for n in aurora.__all__ if inspect.isroutine(getattr(aurora, n))]


# --- La chuleta y la copia empaquetada ----------------------------------------------------------


def test_chuleta_generada_al_dia() -> None:
    current = llmstxt.CHEATSHEET.read_text(encoding="utf-8")
    assert llmstxt.generated_names(current) == ["firmas", "estilo", "tokens"]
    expected = llmstxt.regenerate(current)
    if UPDATE and expected != current:
        llmstxt.write_text(llmstxt.CHEATSHEET, expected)
        current = expected
    assert current == expected, f"Las partes generadas de docs/llms.md no están al día: {REGENERATE}"


def test_copia_empaquetada_al_dia() -> None:
    expected = llmstxt.bundle()
    if UPDATE:
        for stale in set(p.name for p in llmstxt.BUNDLE.glob("*.md")) - set(expected):
            (llmstxt.BUNDLE / stale).unlink()
        for name, text in expected.items():
            llmstxt.write_text(llmstxt.BUNDLE / name, text)
    assert sorted(p.name for p in llmstxt.BUNDLE.glob("*.md")) == sorted(_llmdocs.PAGES)
    for name, text in expected.items():
        current = (llmstxt.BUNDLE / name).read_text(encoding="utf-8")
        assert current == text, f"python/aurora/_docs/{name} no coincide con docs/{name}: {REGENERATE}"


def test_la_chuleta_nombra_toda_la_api() -> None:
    sheet = (_llmdocs.DIR / "llms.md").read_text(encoding="utf-8")
    missing = [n for n in _public_functions() if not re.search(rf"^{n}\(", sheet, re.M)]
    missing += [k for k in _style.Style.__optional_keys__ if k != "key" and f"`{k}`" not in sheet]
    missing += [f"${t}" for t in [*aurora.MIDNIGHT.colors, *aurora.MIDNIGHT.radius] if f"`${t}`" not in sheet]
    assert not missing, f"La chuleta no menciona: {missing}"


def test_la_chuleta_es_compacta() -> None:
    lines = (_llmdocs.DIR / "llms.md").read_text(encoding="utf-8").count("\n")
    assert lines < 400, f"La chuleta tiene {lines} líneas: es para leerla entera, cabe en ~300"


def test_los_programas_de_la_chuleta_funcionan() -> None:
    # Los bloques vivos ya los ejecuta tests/test_docs.py; aquí, los programas normales (el test
    # con Pilot). No llaman a `App.run()`.
    source = llmstxt.CHEATSHEET.read_text(encoding="utf-8")
    programs = [b for b in re.findall(r"^```python\n(.*?)^```", source, re.S | re.M) if "from aurora" in b]
    assert programs
    for code in programs:
        exec(compile(code, "docs/llms.md", "exec"), {"__name__": "chuleta"})


def test_cada_funcion_publica_tiene_su_tema() -> None:
    missing = [n for n in _public_functions() if _llmdocs.find(n) is None]
    assert not missing, f"`aurora docs <nombre>` no encuentra: {missing}"


# --- Markdown limpio y llms.txt -----------------------------------------------------------------


def test_clean_quita_lo_que_no_es_para_modelos() -> None:
    source = """---
hide:
  - navigation
---

# Título { .sr-only }

<div class="hero" markdown>

![Banner](assets/banner.png)

<p class="tagline">Lema de la portada.</p>

[Empezar](guide.md){ .md-button }

</div>

!!! tip "Consejo"

    Texto del consejo.

Ver [el ejemplo](../examples/hello.py#L3).

```python live size=300x100
from aurora import text
dato = 1  # oculto
text("hola")
```

```python
# un comentario no es un encabezado
x = {"a": 1}  # { .no-es-atributo }
```
"""
    out = llmstxt.clean(source, "pagina.md", repo="https://ejemplo.org/repo")
    assert out.startswith("# Título\n\nLema de la portada.\n\n[Empezar](guide.md)\n")
    assert "<div" not in out and "banner.png" not in out and "hide:" not in out
    assert "> **Consejo**\n>\n> Texto del consejo.\n\n" in out
    assert "(https://ejemplo.org/repo/blob/main/examples/hello.py#L3)" in out
    assert '```python\nfrom aurora import text\ntext("hola")\n```' in out
    assert "oculto" not in out and "live" not in out
    assert 'x = {"a": 1}  # { .no-es-atributo }' in out
    assert "\n\n\n" not in out


def test_clean_incluye_los_snippets() -> None:
    out = llmstxt.clean((llmstxt.DOCS / "changelog.md").read_text(encoding="utf-8"), "changelog.md")
    assert out.startswith("# Changelog") and "--8<--" not in out


def test_write_site_publica_llms_txt_y_las_paginas(tmp_path: Path) -> None:
    nav = [
        ("Inicio", "index.md"),
        ("Guía", "guide.md"),
        ("Para LLMs", "llms.md"),
        ("Estabilidad", "stability.md"),
    ]
    written = llmstxt.write_site(tmp_path, nav, site_url="https://ejemplo.org/aurora", description="Resumen.")
    assert {p.name for p in written} == {
        "index.md",
        "guide.md",
        "llms.md",
        "stability.md",
        "llms.txt",
        "llms-full.txt",
    }

    txt = (tmp_path / "llms.txt").read_text(encoding="utf-8")
    assert txt.startswith("# Aurora\n\n> Resumen.\n")
    assert f"Versión {aurora.__version__}" in txt
    docs, optional = txt.split("## Docs")[1].split("## Optional")
    # La chuleta va primero en Docs, aunque en la navegación esté después.
    assert re.findall(r"\]\(https://ejemplo\.org/aurora/(\S+)\)", docs) == ["llms.md", "guide.md", "index.md"]
    assert "(https://ejemplo.org/aurora/stability.md): " in optional
    assert "- [Guía](https://ejemplo.org/aurora/guide.md): En esta guía construimos" in docs

    full = (tmp_path / "llms-full.txt").read_text(encoding="utf-8")
    assert full.startswith(f"# Aurora {aurora.__version__}: documentación completa")
    assert full.index("# Aurora para modelos") < full.index("# Guía: tu primera app")
    assert "python live" not in full and "# oculto" not in full and "<div" not in full
    assert "Qué es API pública" not in full  # stability no es de las páginas de programar
    index = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert "aurora-hero" not in index and "```python\nfrom aurora import App" in index


def test_summary_toma_la_primera_frase() -> None:
    assert llmstxt.summary("# T\n\n> cita\n\nUna frase. Otra frase.\n") == "Una frase"
    assert llmstxt.summary("# T\n\n```python\nx = 1\n```\n\nTexto [con enlace](a.md): y más.\n") == (
        "Texto con enlace"
    )


# --- aurora docs --------------------------------------------------------------------------------


def test_docs_sin_argumentos_imprime_la_chuleta(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["docs"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"# Aurora para modelos (LLM)\n\nVersión instalada: Aurora {aurora.__version__}.")
    assert "\nbutton(label: TextLike" in out and "## Errores frecuentes" in out
    assert "\x1b[" not in out  # sin colores


def test_docs_tema_imprime_su_seccion(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["docs", "button"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("### `button(label, on_click=None, *, variant=")
    assert '"ghost"' in out and "### `card(" not in out

    assert main(["docs", "Pilot"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("## Pilot (tests de interacción)") and "`click(key)`" in out
    assert "## Inspector" not in out

    assert main(["docs", "temas", "y", "tokens"]) == 0
    assert capsys.readouterr().out.startswith("## Temas y tokens")
    assert main(["docs", "style"]) == 0
    assert capsys.readouterr().out.startswith("## Propiedades de estilo")
    assert main(["docs", "switch"]) == 0  # comparte encabezado con checkbox
    assert "`switch(on" in capsys.readouterr().out.partition("\n")[0]
    assert main(["docs", "kanban"]) == 0  # una palabra del título, si solo hay uno
    assert capsys.readouterr().out.startswith("## Tablero kanban")


def test_docs_tema_desconocido_sugiere(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["docs", "buton"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "no hay ningún tema 'buton'. ¿Quisiste decir 'button'?" in captured.err
    assert "aurora docs --search buton" in captured.err


def test_docs_search(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["docs", "--search", "STICK_TO_END"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# Secciones que contienen 'STICK_TO_END'")
    first = out.splitlines()[2]
    assert (
        first.startswith("- Referencia › Componentes › `virtual_list(")
        and "(`aurora docs virtual_list`)" in first
    )
    assert "Recetas › Chat (`aurora docs chat`)" in out

    assert main(["docs", "--search", "zzz-no-existe"]) == 1
    assert "nada contiene" in capsys.readouterr().err


def test_docs_full_y_list(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["docs", "--full"]) == 0
    out = capsys.readouterr().out
    assert out == _llmdocs.full(aurora.__version__)
    for page in _llmdocs.PAGES:
        assert _llmdocs.page_title(page) in out

    assert main(["docs", "--list"]) == 0
    out = capsys.readouterr().out
    assert "- aurora docs pilot: Pilot (tests de interacción)" in out
    assert "  - aurora docs button: `button(" in out


def test_docs_tema_y_opcion_a_la_vez(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["docs", "button", "--full"]) == 2
    assert "no se combina" in capsys.readouterr().err


# --- aurora agents ------------------------------------------------------------------------------


def test_agents_crea_y_actualiza(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["agents", str(tmp_path)]) == 0
    path = tmp_path / "AGENTS.md"
    assert capsys.readouterr().out.strip() == f"{path}: creado"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# AGENTS.md\n\n" + _agents.START)
    assert f"Aurora {aurora.__version__}" in text and "`aurora docs`" in text and "render_png" in text

    path.write_text(text.replace(aurora.__version__, "0.0.1") + "\nNotas propias.\n", encoding="utf-8")
    assert main(["agents", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == f"{path}: actualizado"
    again = path.read_text(encoding="utf-8")
    assert again.count(_agents.START) == 1 and "0.0.1" not in again
    assert again.endswith("\nNotas propias.\n")


def test_agents_no_pisa_un_archivo_existente(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "AGENTS.md"
    path.write_text("# Mi proyecto\n\nUsa tabuladores.\n", encoding="utf-8")
    assert main(["agents", str(path)]) == 0
    assert capsys.readouterr().out.strip() == f"{path}: añadido"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Mi proyecto\n\nUsa tabuladores.\n\n" + _agents.START)
    assert text.endswith(_agents.END + "\n")

    assert main(["agents", str(path), "--force"]) == 0
    assert capsys.readouterr().out.strip() == f"{path}: sobrescrito"
    assert "tabuladores" not in path.read_text(encoding="utf-8")


def test_agents_print_y_carpeta_inexistente(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["agents", "--print"]) == 0
    assert capsys.readouterr().out == _agents.section(aurora.__version__)
    assert main(["agents", str(tmp_path / "no" / "existe")]) == 1
    assert "no existe la carpeta" in capsys.readouterr().err


def test_agents_lista_los_comandos_de_comprobacion(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "Desde la terminal" not in _agents.section("1.0")
    monkeypatch.setattr(_agents, "CHECK_COMMANDS", [("aurora shot app.py", "captura sin ventana")])
    assert "- `aurora shot app.py`: captura sin ventana" in _agents.section("1.0")
