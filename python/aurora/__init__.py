"""Aurora — UI de escritorio declarativa para Python con núcleo nativo en Rust."""

from __future__ import annotations

import asyncio
import sys
import threading
import traceback
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from types import ModuleType
from typing import Any, Literal, TypeVar

from . import _core, animate, reactive
from . import inspector as _inspector
from . import reload as _reload
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
from .resources import resource
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
    "resource",
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

    `inspector=True` permite abrir con F12 el inspector del árbol y el profiler
    de frames (ver `aurora.inspector`). Sin indicarlo, lo activa la variable de
    entorno `AURORA_INSPECTOR=1`.

    `reload=True` activa el hot reload en `run()`: al guardar el script o un
    módulo local, la vista se reconstruye con el código nuevo sin perder el
    estado de los `Signal` (ver `aurora.reload`). Sin indicarlo, lo activa la
    variable de entorno `AURORA_RELOAD=1` (o `aurora dev app.py`).
    """

    def __init__(
        self,
        view: Callable[[], Element],
        *,
        title: str = "Aurora",
        size: tuple[float, float] = (960, 640),
        theme: Theme | Callable[[], Theme] = MIDNIGHT,
        inspector: bool | None = None,
        reload: bool | None = None,
    ) -> None:
        self.view = view
        self.title = title
        self.size = size
        self.theme = theme
        self.inspector = _inspector.enabled(inspector)
        self._inspector = _inspector.Inspector()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_lock = threading.Lock()
        self.reload = _reload.enabled(reload)
        self._reloader: _reload.Reloader | None = None
        # Dentro de una recarga, esta `App` solo presta su vista a la que está en marcha.
        if _reload.context.active:
            _reload.context.created = self

    def _build(self) -> dict:
        if self._reloader is not None:
            self._apply_reload(self._reloader)
        reactive.begin_build()
        try:
            # El tema puede ser reactivo (p. ej. un Signal[Theme]) para alternar claro/oscuro.
            theme = self.theme if isinstance(self.theme, Theme) else self.theme()
            root = self._root() if self._reloader is not None else self.view()
            root.style.setdefault("bg", "$background")
            root.style.setdefault("font_family", theme.font_family)
            root.style.setdefault("color", "$text")
            root.style.setdefault("focus_color", "$primary")
            # Burbuja de tooltip invertida respecto al tema: destaca en claro y en oscuro.
            root.style.setdefault("tooltip_bg", "$text")
            root.style.setdefault("tooltip_color", "$background")
            spec = root.to_spec(theme)
            # Con el panel del inspector abierto, se acopla a la derecha de la vista.
            info = _core.inspection()
            if info is not None and info["open"]:
                spec = self._inspector.dock(spec, info, theme.font_family)
            return spec
        finally:
            reactive.end_build()

    def _apply_reload(self, reloader: _reload.Reloader) -> None:
        """Aplica los cambios pendientes del hot reload: la vista y el tema pasan a los nuevos."""
        if not reloader.pending:
            return
        try:
            app = reloader.apply()
        except _reload.ReloadError as e:
            reloader.error = e.details
            print(e.details, file=sys.stderr, end="", flush=True)
            return
        reloader.error = None
        if isinstance(app, App):
            self.view, self.theme = app.view, app.theme
        print("aurora: recargado", file=sys.stderr, flush=True)

    def _root(self) -> Element:
        """La vista con hot reload: si la recarga o la vista fallan, se muestra el error."""
        reloader = self._reloader
        if reloader is not None and reloader.error is not None:
            return _reload.error_view(reloader.error)
        try:
            return self.view()
        except Exception:
            details = traceback.format_exc()
            print(details, file=sys.stderr, end="", flush=True)
            return _reload.error_view(details)

    def watch(self, main: ModuleType | None = None) -> _reload.Reloader:
        """Activa el hot reload del script `main` (por defecto, `__main__`) sin vigilar los archivos.

        `run()` lo llama solo con `reload=True`; sirve para probarlo con `pilot()`:
        `reloader.check()` detecta los cambios y el siguiente frame los aplica.
        """
        if self._reloader is None:
            self._reloader = _reload.Reloader(main if main is not None else sys.modules["__main__"])
        return self._reloader

    def run(self, *, backend: Literal["auto", "gpu", "cpu"] = "auto") -> None:
        """Abre la ventana y ejecuta la app hasta que se cierre.

        `backend` elige dónde se pinta: `"gpu"` (Vulkan en Windows y Linux, Metal en macOS),
        `"cpu"` o `"auto"` (GPU si se puede iniciar; si no, CPU). Con `"auto"`, la variable de
        entorno `AURORA_BACKEND` puede forzar uno de los otros dos.
        """
        if _reload.context.active:
            _reload.context.ran = self
            return
        if self.reload:
            try:
                self.watch().start()
            except ValueError as e:
                print(f"aurora: hot reload desactivado: {e}", file=sys.stderr)
        try:
            _core.run(self._build, self.title, *self.size, backend, self.inspector)
        finally:
            if self._reloader is not None:
                self._reloader.stop()

    def render_png(self, path: str, *, size: tuple[float, float] | None = None, scale: float = 2.0) -> None:
        """Renderiza la vista a PNG sin ventana (tests de snapshot, CI, previews)."""
        w, h = size or self.size
        _core.render_png(self._build(), w, h, path, scale)

    def pilot(
        self, *, size: tuple[float, float] | None = None, scale: float = 1.0, inspector: bool = False
    ) -> Pilot:
        """Ejecuta la app sin ventana y devuelve un `Pilot` para simular interacción en tests.

        Con `inspector=True` el inspector se abre con `pilot.press("f12")`, como en la ventana.
        """
        w, h = size or self.size
        return Pilot(self._build, w, h, scale, inspector)

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
