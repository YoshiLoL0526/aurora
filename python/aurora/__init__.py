"""Aurora — UI de escritorio declarativa para Python con núcleo nativo en Rust."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from typing import Any, Literal, TypeVar

from . import _core, animate, reactive
from ._core import DragEvent, KeyEvent, Pilot, ScrollEvent
from .canvas import Canvas, Path, canvas
from .charts import chart
from .components import (
    avatar,
    badge,
    button,
    card,
    checkbox,
    divider,
    select,
    stat,
    switch,
    tabs,
    text_input,
    textarea,
    tooltip,
    virtual_list,
)
from .elements import Element, box, column, image, row, scroll, spacer, text
from .reactive import component
from .signal import Signal
from .table import Column, table
from .theme import DAYLIGHT, MIDNIGHT, Theme

__all__ = [
    "DAYLIGHT",
    "MIDNIGHT",
    "App",
    "Canvas",
    "Column",
    "DragEvent",
    "Element",
    "KeyEvent",
    "Path",
    "Pilot",
    "ScrollEvent",
    "Signal",
    "Theme",
    "animate",
    "avatar",
    "badge",
    "box",
    "button",
    "canvas",
    "card",
    "chart",
    "checkbox",
    "column",
    "component",
    "divider",
    "image",
    "row",
    "scroll",
    "select",
    "spacer",
    "stat",
    "switch",
    "table",
    "tabs",
    "text",
    "text_input",
    "textarea",
    "tooltip",
    "virtual_list",
]
__version__ = _core.__version__

T = TypeVar("T")


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
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_lock = threading.Lock()

    def _build(self) -> dict:
        reactive.begin_build()
        try:
            # El tema puede ser reactivo (p. ej. un Signal[Theme]) para alternar claro/oscuro.
            theme = self.theme if isinstance(self.theme, Theme) else self.theme()
            root = self.view()
            root.style.setdefault("bg", "$background")
            root.style.setdefault("font_family", theme.font_family)
            root.style.setdefault("color", "$text")
            root.style.setdefault("focus_color", "$primary")
            # Burbuja de tooltip invertida respecto al tema: destaca en claro y en oscuro.
            root.style.setdefault("tooltip_bg", "$text")
            root.style.setdefault("tooltip_color", "$background")
            return root.to_spec(theme)
        finally:
            reactive.end_build()

    def run(self, *, backend: Literal["auto", "gpu", "cpu"] = "auto") -> None:
        """Abre la ventana y ejecuta la app hasta que se cierre.

        `backend` elige dónde se pinta: `"gpu"` (Vulkan en Windows y Linux, Metal en macOS),
        `"cpu"` o `"auto"` (GPU si se puede iniciar; si no, CPU). Con `"auto"`, la variable de
        entorno `AURORA_BACKEND` puede forzar uno de los otros dos.
        """
        _core.run(self._build, self.title, *self.size, backend)

    def render_png(self, path: str, *, size: tuple[float, float] | None = None, scale: float = 2.0) -> None:
        """Renderiza la vista a PNG sin ventana (tests de snapshot, CI, previews)."""
        w, h = size or self.size
        _core.render_png(self._build(), w, h, path, scale)

    def pilot(self, *, size: tuple[float, float] | None = None, scale: float = 1.0) -> Pilot:
        """Ejecuta la app sin ventana y devuelve un `Pilot` para simular interacción en tests."""
        w, h = size or self.size
        return Pilot(self._build, w, h, scale)

    def spawn(self, coro: Coroutine[Any, Any, T]) -> Future[T]:
        """Ejecuta una corrutina en un bucle `asyncio` en segundo plano.

        El bucle vive en un hilo propio y se crea la primera vez que se llama.
        La corrutina puede cambiar `Signal`: la ventana se actualiza sola.
        """
        return asyncio.run_coroutine_threadsafe(coro, self._background_loop())

    def _background_loop(self) -> asyncio.AbstractEventLoop:
        with self._loop_lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                threading.Thread(target=loop.run_forever, name="aurora-asyncio", daemon=True).start()
                self._loop = loop
            return self._loop
