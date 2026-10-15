"""Stubs del módulo nativo (Rust). La API pública está en `aurora`; esto es interno."""

from typing import Any, Callable

__version__: str

def render_png(tree: dict[str, Any], width: float, height: float, path: str, scale: float = 2.0) -> None:
    """Renderiza un árbol de vista serializado a un archivo PNG, sin ventana."""

def run(
    build: Callable[[], dict[str, Any]],
    title: str = "Aurora",
    width: float = 960.0,
    height: float = 640.0,
) -> None:
    """Abre una ventana y ejecuta el bucle de eventos hasta que se cierre."""
