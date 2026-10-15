"""Aurora — UI de escritorio declarativa para Python con núcleo nativo en Rust."""

from __future__ import annotations

from typing import Callable

from . import _core
from .components import badge, button, card, stat
from .elements import Element, box, column, row, spacer, text
from .signal import Signal
from .theme import MIDNIGHT, Theme

__all__ = [
    "App", "Element", "Signal", "Theme", "MIDNIGHT",
    "box", "column", "row", "text", "spacer",
    "button", "card", "badge", "stat",
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
        theme: Theme = MIDNIGHT,
    ) -> None:
        self.view = view
        self.title = title
        self.size = size
        self.theme = theme

    def _build(self) -> dict:
        root = self.view()
        root.style.setdefault("bg", "$background")
        root.style.setdefault("font_family", self.theme.font_family)
        root.style.setdefault("color", "$text")
        return root.to_spec(self.theme)

    def run(self) -> None:
        _core.run(self._build, self.title, *self.size)

    def render_png(self, path: str, *, size: tuple[float, float] | None = None, scale: float = 2.0) -> None:
        """Renderiza la vista a PNG sin ventana (tests de snapshot, CI, previews)."""
        w, h = size or self.size
        _core.render_png(self._build(), w, h, path, scale)
