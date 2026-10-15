"""Aurora — UI de escritorio declarativa para Python con núcleo nativo en Rust."""

from __future__ import annotations

from collections.abc import Callable

from . import _core
from .components import badge, button, card, stat
from .elements import Element, box, column, row, spacer, text
from .signal import Signal
from .theme import DAYLIGHT, MIDNIGHT, Theme

__all__ = [
    "DAYLIGHT",
    "MIDNIGHT",
    "App",
    "Element",
    "Signal",
    "Theme",
    "badge",
    "box",
    "button",
    "card",
    "column",
    "row",
    "spacer",
    "stat",
    "text",
]
__version__ = _core.__version__


class App:
    """Punto de entrada de una aplicación.

    `view` es una función sin argumentos que devuelve el árbol de la interfaz.
    Se vuelve a llamar cada vez que un evento puede haber cambiado el estado.
    """

    def __init__(
        self,
        view: Callable[[], Element],
        *,
        title: str = "Aurora",
        size: tuple[float, float] = (960, 640),
        theme: Theme | Callable[[], Theme] = MIDNIGHT,
    ) -> None:
        self.view = view
        self.title = title
        self.size = size
        self.theme = theme

    def _build(self) -> dict:
        # El tema puede ser reactivo (p. ej. un Signal[Theme]) para alternar claro/oscuro.
        theme = self.theme() if callable(self.theme) else self.theme
        root = self.view()
        root.style.setdefault("bg", "$background")
        root.style.setdefault("font_family", theme.font_family)
        root.style.setdefault("color", "$text")
        return root.to_spec(theme)

    def run(self) -> None:
        _core.run(self._build, self.title, *self.size)

    def render_png(self, path: str, *, size: tuple[float, float] | None = None, scale: float = 2.0) -> None:
        """Renderiza la vista a PNG sin ventana (tests de snapshot, CI, previews)."""
        w, h = size or self.size
        _core.render_png(self._build(), w, h, path, scale)
