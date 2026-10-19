"""Avisos de obsolescencia: cómo la API pública cambia sin romper de golpe.

Antes de eliminar o renombrar algo público, se marca como obsoleto: sigue
funcionando, pero avisa con `AuroraDeprecationWarning` diciendo desde qué
versión está obsoleto, en cuál se eliminará y qué usar en su lugar. La política
completa (plazos y qué cuenta como API pública) está en `docs/stability.md`.

    @deprecated(since="0.6", removed_in="0.7", instead="aurora.nuevo")
    def viejo(): ...

    @renamed_kwargs(since="0.6", removed_in="0.7", color="tone")
    def badge(label, *, tone="neutral"): ...

Para lo que no es una función entera (un valor de un parámetro, un token del
tema…), `warn(...)` emite el mismo aviso en el punto exacto.
"""

from __future__ import annotations

import functools
import warnings
from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class AuroraDeprecationWarning(FutureWarning):
    """Aviso de que una parte de la API de Aurora está obsoleta.

    Hereda de `FutureWarning` para que se vea por defecto (un
    `DeprecationWarning` se oculta fuera de `__main__`). Para convertirlo en
    error en los tests de una app: `-W error::aurora.AuroraDeprecationWarning`.
    """


def _name(fn: Callable[..., Any]) -> str:
    return getattr(fn, "__qualname__", None) or getattr(fn, "__name__", repr(fn))


def message(what: str, *, since: str, removed_in: str, instead: str | None = None) -> str:
    """El texto del aviso, igual en todos los casos."""
    text = f"{what} está obsoleto desde la versión {since} y se eliminará en la {removed_in}"
    return f"{text}: usa {instead} en su lugar." if instead else f"{text}."


def warn(what: str, *, since: str, removed_in: str, instead: str | None = None, stacklevel: int = 2) -> None:
    """Avisa de que `what` está obsoleto, señalando a quien llama.

    `stacklevel=2` apunta a quien llamó a la función que llama a `warn`; súbelo
    por cada envoltorio intermedio.
    """
    warnings.warn(
        message(what, since=since, removed_in=removed_in, instead=instead),
        AuroraDeprecationWarning,
        stacklevel=stacklevel + 1,
    )


def deprecated(*, since: str, removed_in: str, instead: str | None = None) -> Callable[[F], F]:
    """Marca una función (o método) entera como obsoleta: avisa en cada llamada."""

    def wrap(fn: F) -> F:
        what = f"`{_name(fn)}`"

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            warn(what, since=since, removed_in=removed_in, instead=instead, stacklevel=2)
            return fn(*args, **kwargs)

        doc = message(what, since=since, removed_in=removed_in, instead=instead)
        wrapper.__doc__ = f"Obsoleto: {doc}\n\n{fn.__doc__ or ''}".rstrip()
        return wrapper  # ty: ignore[invalid-return-type]

    return wrap


def renamed_kwargs(*, since: str, removed_in: str, **renames: str) -> Callable[[F], F]:
    """Acepta los nombres viejos de parámetros (`viejo="nuevo"`) avisando.

    Pasar a la vez el nombre viejo y el nuevo es un error (`TypeError`), igual
    que pasar dos veces el mismo argumento.
    """

    def wrap(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for old, new in renames.items():
                if old not in kwargs:
                    continue
                if new in kwargs:
                    raise TypeError(f"{_name(fn)}() recibió a la vez `{old}` y `{new}`; usa `{new}`")
                warn(
                    f"El parámetro `{old}` de `{_name(fn)}()`",
                    since=since,
                    removed_in=removed_in,
                    instead=f"`{new}`",
                    stacklevel=2,
                )
                kwargs[new] = kwargs.pop(old)
            return fn(*args, **kwargs)

        return wrapper  # ty: ignore[invalid-return-type]

    return wrap
