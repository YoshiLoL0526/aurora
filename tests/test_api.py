"""La superficie pública de Aurora, fijada.

`tests/api.txt` lista cada nombre público con su firma. Si un cambio la
altera, este test falla: o el cambio es un accidente, o es intencionado y debe
seguir la política de `docs/stability.md` (marcar lo viejo como obsoleto antes
de quitarlo y anotarlo en el CHANGELOG). Para aceptar el cambio:

    AURORA_UPDATE_API=1 uv run pytest tests/test_api.py
"""

from __future__ import annotations

import inspect
import os
import re
import typing
import warnings
from pathlib import Path
from types import ModuleType, UnionType

import pytest

import aurora
from aurora import _deprecation, animate, dialogs, menus
from aurora._deprecation import AuroraDeprecationWarning, deprecated, renamed_kwargs

SNAPSHOT = Path(__file__).with_name("api.txt")
MODULES: list[tuple[str, ModuleType]] = [
    ("aurora", aurora),
    ("aurora.animate", animate),
    ("aurora.dialogs", dialogs),
    ("aurora.menus", menus),
]


def _signature(obj: object) -> str:
    try:
        sig = str(inspect.signature(obj))  # ty: ignore[invalid-argument-type]
    except (TypeError, ValueError):
        return "(...)"
    # Un tema por defecto se resume: sus colores son estilo, no API.
    sig = re.sub(r"Theme\(colors=\{.*?\}, radius=\{.*?\}, font_family='[^']*'\)", "Theme(...)", sig)
    # Los valores por defecto con identidad (`<… object at 0x…>`) no son estables.
    return re.sub(r" at 0x[0-9a-fA-F]+", "", sig)


def _members(cls: type) -> list[str]:
    lines = []
    for name, member in sorted(vars(cls).items()):
        if name.startswith("_"):  # `__init__` ya sale como firma de la clase
            continue
        if isinstance(member, property):
            lines.append(f"    .{name} (propiedad)")
        elif isinstance(member, staticmethod | classmethod):
            lines.append(f"    .{name}{_signature(member.__func__)}")
        elif callable(member):
            lines.append(f"    .{name}{_signature(member)}")
        else:
            lines.append(f"    .{name}")
    return lines


def surface() -> str:
    """La superficie pública como texto: un nombre (y su firma) por línea."""
    out: list[str] = []
    for modname, module in MODULES:
        out.append(f"[{modname}]")
        for name in sorted(module.__all__):
            obj = getattr(module, name)
            if isinstance(obj, ModuleType):
                out.append(f"{name} (módulo)")
            elif isinstance(obj, type):
                out.append(f"class {name}{_signature(obj)}")
                out.extend(_members(obj))
            elif inspect.isroutine(obj):
                out.append(f"{name}{_signature(obj)}")
            elif typing.get_origin(obj) is not None or isinstance(obj, UnionType):
                out.append(f"{name} = {obj!r}")  # alias de tipo
            else:
                out.append(f"{name}: {type(obj).__name__}")
        out.append("")
    return "\n".join(out)


def test_public_surface_matches_snapshot() -> None:
    current = surface()
    if os.environ.get("AURORA_UPDATE_API"):
        SNAPSHOT.write_text(current, encoding="utf-8", newline="\n")
    expected = SNAPSHOT.read_text(encoding="utf-8")
    assert current == expected, (
        "La API pública cambió. Si es intencionado, sigue docs/stability.md y regenera "
        "tests/api.txt con AURORA_UPDATE_API=1 uv run pytest tests/test_api.py"
    )


@pytest.mark.parametrize(("modname", "module"), MODULES)
def test_all_names_exist(modname: str, module: ModuleType) -> None:
    missing = [n for n in module.__all__ if not hasattr(module, n)]
    assert not missing, f"{modname}.__all__ nombra lo que no existe: {missing}"
    assert len(set(module.__all__)) == len(module.__all__)


def test_deprecated_warns_and_still_works() -> None:
    @deprecated(since="0.6", removed_in="0.7", instead="`nuevo`")
    def viejo(x: int) -> int:
        """Duplica."""
        return x * 2

    with pytest.warns(
        AuroraDeprecationWarning, match=r"`.*viejo` está obsoleto desde la versión 0\.6"
    ) as rec:
        assert viejo(3) == 6
    assert "se eliminará en la 0.7: usa `nuevo`" in str(rec[0].message)
    assert rec[0].filename == __file__  # el aviso señala a quien llama, no al envoltorio
    assert viejo.__name__ == "viejo"
    assert viejo.__doc__ is not None and viejo.__doc__.startswith("Obsoleto:")


def test_renamed_kwargs_maps_old_name() -> None:
    @renamed_kwargs(since="0.6", removed_in="0.7", color="tone")
    def badge(label: str, *, tone: str = "neutral") -> str:
        return f"{label}:{tone}"

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert badge("a", tone="success") == "a:success"  # el nombre nuevo no avisa

    with pytest.warns(AuroraDeprecationWarning, match="parámetro `color`") as rec:
        assert badge("a", color="danger") == "a:danger"  # ty: ignore[unknown-argument]
    assert rec[0].filename == __file__

    with pytest.raises(TypeError, match="a la vez `color` y `tone`"):
        badge("a", color="x", tone="y")  # ty: ignore[unknown-argument]


def test_warning_is_visible_by_default() -> None:
    # FutureWarning se muestra por defecto fuera de `__main__`; DeprecationWarning no.
    assert issubclass(AuroraDeprecationWarning, FutureWarning)
    assert aurora.AuroraDeprecationWarning is _deprecation.AuroraDeprecationWarning
