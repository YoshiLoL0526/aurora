"""Diálogos nativos del sistema: abrir y guardar archivos y carpetas.

Las funciones son **síncronas**: mientras el diálogo está abierto, la app
espera (el sistema corre su propio bucle de mensajes) y el GIL se suelta, así
que los hilos y las corrutinas de `app.spawn` siguen trabajando. Devuelven la
ruta elegida (`str`) o `None` si se cancela; `open_files` devuelve una lista
(vacía si se cancela).

    from aurora import dialogs

    ruta = dialogs.open_file(title="Abrir informe", filters=[("Texto", ["txt", "md"])])
    if ruta is not None:
        ...

La ventana desde la que se llama (su vista o uno de sus manejadores) es el
padre del diálogo: sale modal sobre ella. En los tests, sustitúyelas por un
doble (`monkeypatch.setattr(dialogs, "open_file", ...)`) — un test sin pantalla
no puede abrir un diálogo de verdad.
"""

from __future__ import annotations

from collections.abc import Sequence
from os import PathLike

from . import _core

#: Filtros de tipos de archivo: pares `(nombre, extensiones)`.
Filters = Sequence[tuple[str, Sequence[str]]]


def _spec(filters: Filters | None) -> list[tuple[str, list[str]]] | None:
    """Normaliza los filtros a listas (lo que espera el núcleo)."""
    if filters is None:
        return None
    return [(name, list(extensions)) for name, extensions in filters]


def open_file(
    *,
    title: str | None = None,
    directory: str | PathLike[str] | None = None,
    filters: Filters | None = None,
) -> str | None:
    """Pide un archivo existente y devuelve su ruta, o `None` si se cancela.

    `filters` son pares `(nombre, extensiones)`, por ejemplo
    `[("Imágenes", ["png", "jpg"]), ("Todo", ["*"])]`.
    """
    return _core.open_file(title, directory, _spec(filters))


def open_files(
    *,
    title: str | None = None,
    directory: str | PathLike[str] | None = None,
    filters: Filters | None = None,
) -> list[str]:
    """Pide uno o varios archivos existentes; devuelve sus rutas (vacío si se cancela)."""
    return _core.open_files(title, directory, _spec(filters))


def save_file(
    *,
    title: str | None = None,
    directory: str | PathLike[str] | None = None,
    default_name: str | None = None,
    filters: Filters | None = None,
) -> str | None:
    """Pide dónde guardar y devuelve la ruta elegida, o `None` si se cancela.

    No escribe nada: guardar el contenido es cosa de quien llama.
    """
    return _core.save_file(title, directory, default_name, _spec(filters))


def pick_folder(
    *,
    title: str | None = None,
    directory: str | PathLike[str] | None = None,
) -> str | None:
    """Pide una carpeta y devuelve su ruta, o `None` si se cancela."""
    return _core.pick_folder(title, directory)


__all__ = ["Filters", "open_file", "open_files", "pick_folder", "save_file"]
