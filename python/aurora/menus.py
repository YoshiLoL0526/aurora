"""Descripciones de menús nativos: la barra de la app, el menú de la bandeja y
los contextuales.

Un menú es una lista de dicts que el núcleo traduce a menús del sistema:

    from aurora import menus

    App(
        view,
        menu=menus.bar(
            menus.submenu(
                "Archivo",
                menus.item("Abrir…", abrir, shortcut="mod+o"),
                menus.item("Guardar", guardar, shortcut="mod+s"),
                menus.separator(),
                menus.item("Salir", app.quit),
            ),
            menus.submenu("Edición", menus.predefined("copy"), menus.predefined("paste")),
        ),
    )

La descripción es la misma para la barra (`App(menu=...)`), el menú de la
bandeja (`app.tray(menu=...)`) y los menús contextuales
(`on_context_menu=[...]`).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

#: Entradas estándar que entiende el núcleo (`menus.predefined(...)`).
PREDEFINED = frozenset(
    {
        "about",
        "bring_all_to_front",
        "close_window",
        "copy",
        "cut",
        "delete",
        "fullscreen",
        "hide",
        "hide_others",
        "maximize",
        "minimize",
        "paste",
        "quit",
        "redo",
        "select_all",
        "services",
        "show_all",
        "undo",
    }
)


def item(
    label: str,
    on_click: Callable[[], Any],
    *,
    shortcut: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """Una opción del menú que llama a `on_click` al elegirla.

    `shortcut` es un atajo del sistema: `"ctrl+o"`, `"mod+s"` (`mod` es Control
    fuera de macOS y Comando en macOS), `"shift+alt+f"`, `"f5"`… Los atajos de
    la barra los gestiona el sistema (en macOS, la app no los ve como teclas).
    """
    return {
        "type": "item",
        "label": label,
        "enabled": bool(enabled),
        "action": on_click,
        "shortcut": shortcut,
    }


def separator() -> dict[str, Any]:
    """Una línea separadora."""
    return {"type": "separator"}


def submenu(label: str, *items: dict[str, Any]) -> dict[str, Any]:
    """Un submenú con sus entradas."""
    return {"type": "submenu", "label": label, "items": list(items)}


def predefined(name: str) -> dict[str, Any]:
    """Una entrada estándar del sistema: `"copy"`, `"paste"`, `"select_all"`,
    `"undo"`, `"quit"`, `"close_window"`, `"minimize"`, `"about"`…"""
    if name not in PREDEFINED:
        raise ValueError(f"entrada estándar desconocida: {name!r} (válidas: {', '.join(sorted(PREDEFINED))})")
    return {"type": "predefined", "name": name}


def bar(*items: dict[str, Any]) -> Sequence[dict[str, Any]]:
    """La barra de la app, para `App(view, menu=menus.bar(...))`.

    Es azúcar: `menus.bar(a, b)` es `[a, b]`. En macOS, el núcleo añade delante
    el submenú estándar de la app (Acerca de, Ocultar, Salir…).
    """
    return list(items)


__all__ = ["PREDEFINED", "bar", "item", "predefined", "separator", "submenu"]
