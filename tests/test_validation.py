"""Validación de props, manejadores y tokens: errores claros con sugerencia.

La lista de props válidas es `aurora._style.Style`; aquí se comprueba que
coincide con lo que lee el núcleo (`KEYS` en `src/spec.rs`) y con los eventos
que despacha, y que `_style_variants.py` (generado a partir de `Style`) está al
día. Para regenerarlo:

    AURORA_UPDATE_API=1 uv run pytest tests/test_validation.py
"""

from __future__ import annotations

import ast
import inspect
import os
import re
from pathlib import Path

import pytest

import aurora
from aurora import (
    MIDNIGHT,
    ThemeTokenError,
    avatar,
    box,
    button,
    card,
    chart,
    checkbox,
    column,
    row,
    text,
    text_input,
)
from aurora._style import EVENT_NAMES, STYLE_NAMES, Style

ROOT = Path(__file__).parents[1]
SPEC = ROOT / "src" / "spec.rs"
STYLE_SOURCE = ROOT / "python" / "aurora" / "_style.py"
VARIANTS = ROOT / "python" / "aurora" / "_style_variants.py"

# Claves de `KEYS` que son del nodo, no de su estilo.
NODE_KEYS = {"chart", "children", "draw", "handlers", "key", "kind", "memo", "style", "text"}


def test_prop_desconocida_sugiere_la_correcta():
    with pytest.raises(TypeError, match=r"^column\(\) no acepta la prop 'bgg'\. ¿Quisiste decir 'bg'\?$"):
        column(bgg="red")
    with pytest.raises(TypeError, match=r"row\(\) no acepta la prop 'gapp'\. ¿Quisiste decir 'gap'\?"):
        row(gapp=3)
    with pytest.raises(TypeError, match=r"text\(\) no acepta la prop 'colr'\. ¿Quisiste decir 'color'\?"):
        text("x", colr="red")


def test_el_mensaje_nombra_el_componente_que_se_llamo():
    with pytest.raises(TypeError, match=r"^card\(\) no acepta la prop 'raduis'\. ¿Quisiste decir 'radius'\?"):
        card(raduis=4)
    with pytest.raises(TypeError, match=r"^chart\(\) no acepta la prop 'heigth'"):
        chart([1, 2, 3], heigth=100)
    with pytest.raises(TypeError, match=r"^text_input\(\) no acepta"):
        text_input("", paddin=4)


def test_manejador_mal_escrito():
    with pytest.raises(
        TypeError, match=r"button\(\) no acepta la prop 'onclick'\. ¿Quisiste decir 'on_click'\?"
    ):
        button("a", onclick=print)
    with pytest.raises(
        TypeError, match=r"box\(\) no acepta el manejador 'on_clik'\. ¿Quisiste decir 'on_click'\?"
    ):
        box(on_clik=print)
    with pytest.raises(TypeError, match=r"checkbox\(\) no acepta el manejador 'on_hover'"):
        checkbox(False, on_hover=print)


def test_prop_sin_parecido_remite_a_la_referencia():
    with pytest.raises(TypeError, match=r"no acepta la prop 'zzz'\. Las propiedades válidas"):
        box(zzz=1)


def test_una_prop_desconocida_falla_aunque_valga_none():
    with pytest.raises(TypeError, match="'bgg'"):
        box(bgg=None)


def test_el_ejemplo_del_problema_falla_en_la_primera_prop():
    with pytest.raises(TypeError, match="'bgg'"):
        column(bgg="red", gapp=3)[text("x", colr="red"), button("a", onclick=print)]


def test_las_props_validas_y_los_alias_siguen_funcionando():
    el = text("x", size=12, weight=600, family="Inter", on_click=print, role="button")
    assert el.style == {"font_size": 12, "font_weight": 600, "font_family": "Inter", "role": "button"}
    assert el.handlers == {"click": print}
    assert avatar("Ana", size=40).style["width"] == 40


def test_token_mal_escrito_sugiere_el_correcto():
    with pytest.raises(ThemeTokenError) as info:
        box(bg="$primry").to_spec(MIDNIGHT)
    assert str(info.value) == "token de tema desconocido en 'bg': '$primry'. ¿Quisiste decir '$primary'?"
    assert info.value.token == "$primry"
    assert info.value.prop == "bg"


def test_token_dentro_de_una_tupla_y_de_radio():
    with pytest.raises(ThemeTokenError, match=r"en 'shadow': '\$shadw'\. ¿Quisiste decir '\$shadow'\?"):
        box(shadow=(0, 4, 8, "$shadw")).to_spec(MIDNIGHT)
    with pytest.raises(ThemeTokenError, match=r"¿Quisiste decir '\$full'\?"):
        box(radius="$ful").to_spec(MIDNIGHT)


def test_el_error_de_token_sigue_siendo_un_keyerror():
    with pytest.raises(KeyError):
        MIDNIGHT.resolve("$nada")
    with pytest.raises(ThemeTokenError, match=r"^token de tema desconocido: '\$nada'\.$"):
        MIDNIGHT.resolve("$nada")


def _rust_keys() -> set[str]:
    source = SPEC.read_text(encoding="utf-8")
    table = re.search(r"const KEYS: \[&str; \d+\] = \[(.*?)\];", source, re.S)
    assert table, "no se encontró `KEYS` en src/spec.rs"
    return set(re.findall(r'"([a-z_]+)"', table.group(1)))


def _rust_events() -> set[str]:
    events: set[str] = set()
    for path in (ROOT / "src").rglob("*.rs"):
        source = path.read_text(encoding="utf-8")
        events |= set(re.findall(r'\b(?:handler|contains_key|keys_with)\("([a-z_]+)"\)', source))
        events |= set(re.findall(r'\b(?:dispatch|call)\([^;()]*?"([a-z_]+)"', source))
    return events


def test_las_props_coinciden_con_las_que_lee_el_nucleo():
    # Lo que acepta `Style` (sin alias) es lo que `spec::parse` lee del estilo.
    assert set(STYLE_NAMES.values()) == _rust_keys() - NODE_KEYS


def test_los_manejadores_coinciden_con_los_eventos_del_nucleo():
    assert set(EVENT_NAMES.values()) == _rust_events()


def _styled_functions() -> dict[str, list[str]]:
    """Las funciones públicas con `**estilo` y sus parámetros que son también claves de `Style`."""
    keys = Style.__optional_keys__
    out = {}
    for name in sorted(aurora.__all__):
        fn = getattr(aurora, name)
        if not inspect.isfunction(fn):
            continue
        params = inspect.signature(fn).parameters
        if any(p.kind is p.VAR_KEYWORD for p in params.values()):
            out[name] = sorted(set(params) & keys)
    return out


def _variant_name(function: str) -> str:
    return "".join(part.capitalize() for part in function.split("_")) + "Style"


def _render_variants() -> str:
    """`_style_variants.py`: una copia de `Style` por cada función cuyos
    parámetros se solapan con sus claves (un `**kwargs: Unpack[...]` no puede
    repetir el nombre de un parámetro), sin esas claves."""
    source = STYLE_SOURCE.read_text(encoding="utf-8")
    cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == "Style")
    lines = source.splitlines()
    first = cls.body[1].lineno - 1  # tras el docstring
    body = lines[first : cls.end_lineno]
    # Los comentarios de sección se conservan; cada campo es una línea.
    head = [
        '"""Variantes de `Style` sin los parámetros propios de cada componente.',
        "",
        "Generado por `tests/test_validation.py` a partir de `aurora._style.Style`: no",
        "lo edites a mano. Para regenerarlo:",
        "",
        "    AURORA_UPDATE_API=1 uv run pytest tests/test_validation.py",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import os",
        "from collections.abc import Callable, Sequence",
        "from typing import Any, Literal, TypedDict",
        "",
        "from ._style import Align, Color, Cursor, Edges, Handler, Justify, Length, Prop, WindowDrag",
    ]
    out = head
    for function, overlap in _styled_functions().items():
        if not overlap:
            continue
        drop = set(overlap)
        out += ["", "", f"class {_variant_name(function)}(TypedDict, total=False):"]
        out.append(f'    """`Style` sin las claves que son parámetros de `{function}()`."""')
        out.append("")
        for line in body:
            field = re.match(r"\s+([a-z_]+):", line)
            if field and field.group(1) in drop:
                continue
            out.append(line)
    return "\n".join(out) + "\n"


def test_las_variantes_de_style_estan_al_dia():
    expected = _render_variants()
    if os.environ.get("AURORA_UPDATE_API"):
        VARIANTS.write_text(expected, encoding="utf-8", newline="\n")
    current = VARIANTS.read_text(encoding="utf-8") if VARIANTS.exists() else ""
    assert current == expected, (
        "python/aurora/_style_variants.py no está al día con `Style` o con las firmas: "
        "AURORA_UPDATE_API=1 uv run pytest tests/test_validation.py"
    )


def test_cada_funcion_con_estilo_anota_su_variante():
    for function, overlap in _styled_functions().items():
        params = inspect.signature(getattr(aurora, function)).parameters
        annotation = next(p.annotation for p in params.values() if p.kind is p.VAR_KEYWORD)
        expected = f"Unpack[{_variant_name(function) if overlap else 'Style'}]"
        assert annotation == expected, f"{function}(): **estilo debe anotarse como {expected}"
