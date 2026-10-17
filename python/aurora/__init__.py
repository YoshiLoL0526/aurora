"""Aurora — UI de escritorio declarativa para Python con núcleo nativo en Rust."""

from __future__ import annotations

import asyncio
import sys
import threading
import traceback
from collections.abc import Callable, Coroutine, Sequence
from concurrent.futures import Future
from os import PathLike
from types import ModuleType
from typing import Any, Literal, TypeVar

from . import _core, _motion, animate, dialogs, menus, reactive
from . import inspector as _inspector
from . import reload as _reload
from ._core import DragEvent, KeyEvent, Pilot, ScrollEvent
from .canvas import Canvas, Path, canvas
from .charts import chart
from .components import (
    accordion,
    avatar,
    badge,
    button,
    card,
    checkbox,
    dialog,
    divider,
    field,
    menu,
    pages,
    progress,
    radio,
    segmented,
    select,
    skeleton,
    slider,
    spinner,
    stat,
    switch,
    tabs,
    text_input,
    textarea,
    toast,
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
    "Window",
    "accordion",
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
    "dialog",
    "dialogs",
    "divider",
    "field",
    "image",
    "menu",
    "menus",
    "pages",
    "progress",
    "radio",
    "resource",
    "row",
    "scroll",
    "segmented",
    "select",
    "skeleton",
    "slider",
    "spacer",
    "spinner",
    "stat",
    "switch",
    "table",
    "tabs",
    "text",
    "text_input",
    "textarea",
    "toast",
    "tooltip",
    "virtual_list",
]
__version__ = _core.__version__

T = TypeVar("T")


class App:
    """Punto de entrada de una aplicación.

    `view` es una función sin argumentos que devuelve el árbol de la ventana
    principal. Se vuelve a llamar cada vez que un evento puede haber cambiado
    el estado. Con `app.window(...)` se añaden ventanas (ver `Window`).

    `inspector=True` permite abrir con F12 el inspector del árbol y el profiler
    de frames (ver `aurora.inspector`). Sin indicarlo, lo activa la variable de
    entorno `AURORA_INSPECTOR=1`.

    `menu` describe la barra de menús de la app (Windows y macOS) con
    `aurora.menus`: `App(view, menu=menus.bar(menus.submenu("Archivo", ...)))`.
    En Linux no hay barra nativa: para eso está el componente `menu` dentro de
    la interfaz.

    `reload=True` activa el hot reload en `run()`: al guardar el script o un
    módulo local, la vista se reconstruye con el código nuevo sin perder el
    estado de los `Signal` (ver `aurora.reload`). Sin indicarlo, lo activa la
    variable de entorno `AURORA_RELOAD=1` (o `aurora dev app.py`).

    `motion=False` desactiva las animaciones por defecto de los componentes
    (switchs, casillas, pestañas, menús…): los cambios son inmediatos. Sin
    indicarlo, lo decide la variable de entorno `AURORA_MOTION` (`0`, `false`,
    `no` u `off` las desactivan).
    """

    def __init__(
        self,
        view: Callable[[], Element],
        *,
        title: str = "Aurora",
        size: tuple[float, float] = (960, 640),
        theme: Theme | Callable[[], Theme] = MIDNIGHT,
        menu: Sequence[dict[str, Any]] | None = None,
        inspector: bool | None = None,
        reload: bool | None = None,
        motion: bool | None = None,
    ) -> None:
        self.view = view
        self.title = title
        self.size = size
        self.theme = theme
        self.menu = list(menu) if menu is not None else None
        self.inspector = _inspector.enabled(inspector)
        self._inspector = _inspector.Inspector()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_lock = threading.Lock()
        self.reload = _reload.enabled(reload)
        self._reloader: _reload.Reloader | None = None
        self.motion = _motion.enabled(motion)
        self.running = False
        # La bandeja (si la hay) mantiene la app viva sin ventanas.
        self._keep_alive = False
        # La ventana principal, si alguien pide su mango (`app.main`).
        self._main: Window | None = None
        self._windows: dict[int, Window] = {}
        self._next_id = 1
        # Dentro de una recarga, esta `App` solo presta su vista a la que está en marcha.
        if _reload.context.active:
            _reload.context.created = self

    def window(
        self,
        view: Callable[[], Element],
        *,
        title: str = "Aurora",
        size: tuple[float, float] | None = None,
        resizable: bool = True,
        on_close: Callable[[], Any] | None = None,
    ) -> Window:
        """Crea una ventana de la app, con su propia vista.

        Las creadas antes de `run()` se abren al arrancar; las creadas en
        marcha, al momento. `size` por defecto es el de la ventana principal.

        `on_close` se llama al intentar cerrar la ventana (botón del sistema o
        `close()`): si devuelve un valor falso, el cierre se cancela — por
        ejemplo, para pedir confirmación con un diálogo.
        """
        window = Window(
            self,
            view,
            title=title,
            size=size or self.size,
            resizable=resizable,
            on_close=on_close,
        )
        if self.running:
            window.open()
        return window

    def windows(self) -> list[Window]:
        """Las ventanas creadas con `window(...)`, en orden (sin la principal)."""
        return list(self._windows.values())

    @property
    def main(self) -> Window:
        """La ventana principal, como un `Window`.

        Sirve para lo mismo que las demás: cambiar su `title` o su `size` en
        marcha, cerrarla y reabrirla (útil con la bandeja del sistema) o ponerle
        un `on_close` que cancele el cierre (p. ej. para pedir confirmación).
        Su vista es la de la `App` (`view`), así que el hot reload la mantiene.
        """
        if self._main is None:
            self._main = _MainWindow(self)
        return self._main

    def _all_windows(self) -> list[Window]:
        """La principal y las adicionales, en orden de creación."""
        return [self.main, *self._windows.values()]

    def quit(self) -> None:
        """Cierra todas las ventanas y termina la app. Segura desde cualquier hilo."""
        _core.quit()

    def tray(
        self,
        icon: str | PathLike[str] | bytes,
        *,
        tooltip: str | None = None,
        menu: Sequence[dict[str, Any]] | None = None,
        on_click: Callable[[str], Any] | None = None,
        on_double_click: Callable[[str], Any] | None = None,
        template: bool = False,
    ) -> None:
        """Pone (o reemplaza) la bandeja del sistema: icono, tooltip y menú.

        `icon` es una ruta o los bytes de un PNG/SVG. El menú se describe con
        `aurora.menus` (`menus.item("Abrir", abrir)`, `menus.separator()`,
        `menus.submenu(...)`). Mientras haya bandeja, la app sigue viva aunque
        se cierren todas las ventanas: `app.quit()` la termina.

        `on_click(button)` y `on_double_click(button)` reciben el botón
        (`"left"`, `"right"` o `"middle"`); con menú, el clic izquierdo suele
        abrirlo (en macOS siempre). `template=True` (macOS) pinta el icono con
        el color del sistema: dibújalo en blanco y negro con transparencia.
        """
        self._keep_alive = True
        items = None if menu is None else list(menu)
        _core.tray_show(icon, tooltip, items, on_click, on_double_click, template)

    def tray_hide(self) -> None:
        """Quita la bandeja; sin ella, la app vuelve a terminar con su última ventana."""
        self._keep_alive = False
        _core.tray_hide()

    def notify(
        self,
        title: str,
        body: str = "",
        *,
        icon: str | PathLike[str] | None = None,
    ) -> None:
        """Muestra una notificación del sistema.

        `title` y `body` son el encabezado y el texto; `icon` (opcional), una
        ruta a un PNG/SVG, donde el sistema lo admita. El aviso lo pinta el
        sistema: Centro de notificaciones en Windows y macOS, y aviso del
        demonio de notificaciones en Linux (GNOME y KDE lo traen).

        Se puede llamar desde cualquier hilo —por ejemplo desde una tarea de
        `app.spawn()` con la ventana cerrada— y también sin app en marcha. Si
        el sistema no admite notificaciones (Linux sin demonio, macOS sin app
        firmada, Windows sin AppUserModelID registrado), se avisa por stderr y
        la app sigue. En esta versión no hay callback de clic.
        """
        _core.notify(title, body, icon)

    def _register(self, window: Window) -> int:
        window_id = self._next_id
        self._next_id += 1
        self._windows[window_id] = window
        return window_id

    def _notify_closed(self, window_id: int) -> None:
        """El núcleo avisa al cerrarse una ventana (botón del sistema, error o `quit()`)."""
        window = self._windows.get(window_id)
        if window is None and window_id == 0:
            window = self._main
        if window is not None:
            window._open = False
            window._created = False

    def _build_view(self, owner: App | Window) -> dict:
        """Serializa la vista de `owner` (la `App` o una `Window`), con tema, movimiento e inspector.

        La vista se lee **después** de aplicar la recarga pendiente: la recarga
        pudo haber sustituido `owner.view` por la del módulo nuevo.
        """
        if self._reloader is not None:
            self._apply_reload(self._reloader)
        reactive.begin_build(owner)
        # Los componentes leen el interruptor de movimiento al construirse.
        previous_motion = _motion.activate(self.motion)
        try:
            # El tema puede ser reactivo (p. ej. un Signal[Theme]) para alternar claro/oscuro.
            theme = self.theme if isinstance(self.theme, Theme) else self.theme()
            root = self._root(owner.view) if self._reloader is not None else owner.view()
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
            _motion.activate(previous_motion)
            reactive.end_build()

    def _build(self) -> dict:
        """La vista de la ventana principal (lo que consume el núcleo)."""
        return self._build_view(self)

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
            self._sync_windows(app)
        print("aurora: recargado", file=sys.stderr, flush=True)

    def _sync_windows(self, app: App) -> None:
        """Pasa las ventanas del código recargado a la app en marcha, por orden de creación."""
        mine = list(self._windows.values())
        theirs = list(app._windows.values())
        for window, fresh in zip(mine, theirs, strict=False):
            window.view = fresh.view
            window._title, window._size = fresh._title, fresh._size
            window.resizable, window.on_close = fresh.resizable, fresh.on_close
        for extra in mine[len(theirs) :]:
            extra.close()
        for fresh in theirs[len(mine) :]:
            window = self.window(
                fresh.view,
                title=fresh._title,
                size=fresh._size,
                resizable=fresh.resizable,
                on_close=fresh.on_close,
            )
            if not fresh._open:
                window.close()

    def _root(self, view: Callable[[], Element]) -> Element:
        """La vista con hot reload: si la recarga o la vista fallan, se muestra el error."""
        reloader = self._reloader
        if reloader is not None and reloader.error is not None:
            return _reload.error_view(reloader.error)
        try:
            return view()
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

    def run(self, *, backend: Literal["auto", "gpu", "cpu"] = "auto", keep_alive: bool | None = None) -> None:
        """Abre las ventanas y ejecuta la app hasta que se cierren todas.

        `backend` elige dónde se pinta: `"gpu"` (Vulkan en Windows y Linux, Metal en macOS),
        `"cpu"` o `"auto"` (GPU si se puede iniciar; si no, CPU). Con `"auto"`, la variable de
        entorno `AURORA_BACKEND` puede forzar uno de los otros dos.

        `keep_alive=True` mantiene la app en marcha aunque no queden ventanas (para la
        bandeja del sistema) hasta que se llame a `quit()`. Sin indicarlo, decide la app.
        """
        if _reload.context.active:
            _reload.context.ran = self
            return
        if self.running:
            raise RuntimeError("la app ya está en marcha")
        if self.reload:
            try:
                self.watch().start()
            except ValueError as e:
                print(f"aurora: hot reload desactivado: {e}", file=sys.stderr)
        windows = []
        for window in self._all_windows():
            if window._open:
                windows.append(window._config())
                window._created = True
        keep = self._keep_alive if keep_alive is None else keep_alive
        if not windows and not keep:
            raise RuntimeError("no hay ninguna ventana que abrir: todas están cerradas")
        self.running = True
        try:
            _core.run(windows, backend, self.inspector, keep, self.menu)
        finally:
            self.running = False
            if self._reloader is not None:
                self._reloader.stop()
            for window in self._all_windows():
                window._open = False
                window._created = False

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


class Window:
    """Una ventana de la app, creada con `app.window(view)`.

    Las creadas antes de `run()` se abren al arrancar la app; `close()` la
    cierra sin olvidar su vista, y `open()` la vuelve a abrir. `title` y `size`
    se pueden cambiar en marcha, desde cualquier hilo.
    """

    def __init__(
        self,
        app: App,
        view: Callable[[], Element],
        *,
        title: str = "Aurora",
        size: tuple[float, float] = (960, 640),
        resizable: bool = True,
        on_close: Callable[[], Any] | None = None,
        _id: int | None = None,
    ) -> None:
        self._app = app
        # La ventana principal (id 0) no se registra: la tiene la `App`.
        self._id = app._register(self) if _id is None else _id
        self.view = view
        self.resizable = resizable
        self.on_close = on_close
        self._title = title
        self._size = size
        # `_open`: debe estar abierta; `_created`: ya existe en el núcleo.
        self._open = True
        self._created = False

    def __repr__(self) -> str:
        state = "abierta" if self._open else "cerrada"
        return f"<Window {self._id} {self._title!r} {state}>"

    @property
    def title(self) -> str:
        """El título de la ventana (se puede cambiar en marcha)."""
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        self._title = str(value)
        if self._app.running and self._created:
            _core.window_set(self._id, title=self._title)

    @property
    def size(self) -> tuple[float, float]:
        """El tamaño de la ventana en píxeles lógicos (se puede cambiar en marcha)."""
        return self._size

    @size.setter
    def size(self, value: tuple[float, float]) -> None:
        self._size = (float(value[0]), float(value[1]))
        if self._app.running and self._created:
            _core.window_set(self._id, size=self._size)

    @property
    def is_open(self) -> bool:
        """Si la ventana está abierta (o pendiente de abrir al arrancar la app)."""
        return self._open

    def open(self) -> None:
        """Abre la ventana (segura desde cualquier hilo). Si ya está abierta, no hace nada."""
        self._open = True
        if self._app.running and not self._created:
            self._created = True
            _core.window_open(
                self._id,
                self._build,
                self._title,
                self._size,
                self.resizable,
                self.on_close,
                self._app._notify_closed,
            )

    def close(self) -> None:
        """Cierra la ventana sin olvidar su vista; `open()` la vuelve a abrir."""
        self._open = False
        if self._app.running and self._created:
            self._created = False
            _core.window_close(self._id)

    def _config(self) -> dict:
        """La ventana como la espera `_core.run`."""
        return {
            "id": self._id,
            "build": self._build,
            "title": self._title,
            "size": self._size,
            "resizable": self.resizable,
            "on_close": self.on_close,
            "on_closed": self._app._notify_closed,
        }

    def _build(self) -> dict:
        """La vista de esta ventana (lo que consume el núcleo)."""
        return self._app._build_view(self)

    def render_png(self, path: str, *, size: tuple[float, float] | None = None, scale: float = 2.0) -> None:
        """Renderiza la vista de esta ventana a PNG sin abrir ventana."""
        w, h = size or self._size
        _core.render_png(self._build(), w, h, path, scale)

    def pilot(
        self, *, size: tuple[float, float] | None = None, scale: float = 1.0, inspector: bool = False
    ) -> Pilot:
        """Ejecuta la vista de esta ventana sin ventana, para tests de interacción."""
        w, h = size or self._size
        return Pilot(self._build, w, h, scale, inspector)


class _MainWindow(Window):
    """La ventana principal (`app.main`): su vista es la de la `App`.

    Hereda todo el `Window` (título, tamaño, `close()`/`open()`, `pilot()`,
    `render_png()`), pero construye la vista de la app: si el hot reload
    sustituye `app.view`, la principal lo sigue sin sincronizar nada.
    """

    def __init__(self, app: App) -> None:
        super().__init__(app, app.view, title=app.title, size=app.size, _id=0)

    def _build(self) -> dict:
        return self._app._build()
