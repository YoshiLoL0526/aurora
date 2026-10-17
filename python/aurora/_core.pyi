"""Stubs del módulo nativo (Rust). La API pública está en `aurora`; esto es interno."""

from os import PathLike
from typing import Any, Callable

__version__: str

def render_png(tree: dict[str, Any], width: float, height: float, path: str, scale: float = 2.0) -> None:
    """Renderiza un árbol de vista serializado a un archivo PNG, sin ventana."""

def run(
    windows: list[dict[str, Any]],
    backend: str = "auto",
    inspector: bool = False,
    keep_alive: bool = False,
    menu: list[dict[str, Any]] | None = None,
) -> None:
    """Abre las ventanas y ejecuta el bucle de eventos hasta que se cierren.

    `windows`: una lista de dicts con `id`, `build`, `title`, `size`
    (`(ancho, alto)`), `resizable`, `on_close` y `on_closed`; la primera es la
    principal: si no se puede crear, `run` falla (`RuntimeError`).
    `backend`: `"auto"`, `"gpu"` o `"cpu"` (`ValueError` con otro valor).
    `inspector`: F12 abre el inspector del árbol y el profiler de frames.
    `keep_alive`: la app sigue viva (sin ventanas) hasta que se llame a `quit()`.
    `menu`: la barra de menús de la app (la descripción de `aurora.menus`);
    en Windows y macOS.
    """

def window_open(
    id: int,
    build: Callable[[], dict[str, Any]],
    title: str,
    size: tuple[float, float],
    resizable: bool = True,
    on_close: Callable[[], Any] | None = None,
    on_closed: Callable[[int], Any] | None = None,
) -> None:
    """Abre una ventana nueva (segura desde cualquier hilo; la abre el bucle)."""

def window_close(id: int) -> None:
    """Cierra la ventana con esa id (segura desde cualquier hilo)."""

def window_set(id: int, title: str | None = None, size: tuple[float, float] | None = None) -> None:
    """Cambia el título, el tamaño o ambos de una ventana abierta."""

def quit() -> None:
    """Cierra todas las ventanas y termina la app. Segura desde cualquier hilo."""

def wake() -> None:
    """Pide reconstruir la vista y despierta el bucle de eventos. Seguro desde cualquier hilo."""

def open_file(
    title: str | None = None,
    directory: str | PathLike[str] | None = None,
    filters: list[tuple[str, list[str]]] | None = None,
) -> str | None:
    """Pide un archivo existente (diálogo nativo, síncrono). Ruta o `None`."""

def open_files(
    title: str | None = None,
    directory: str | PathLike[str] | None = None,
    filters: list[tuple[str, list[str]]] | None = None,
) -> list[str]:
    """Pide varios archivos existentes (diálogo nativo, síncrono). Rutas o lista vacía."""

def save_file(
    title: str | None = None,
    directory: str | PathLike[str] | None = None,
    default_name: str | None = None,
    filters: list[tuple[str, list[str]]] | None = None,
) -> str | None:
    """Pide dónde guardar (diálogo nativo, síncrono). Ruta o `None`; no escribe nada."""

def pick_folder(title: str | None = None, directory: str | PathLike[str] | None = None) -> str | None:
    """Pide una carpeta (diálogo nativo, síncrono). Ruta o `None`."""

def tray_show(
    icon: str | PathLike[str] | bytes,
    tooltip: str | None = None,
    menu: list[dict[str, Any]] | None = None,
    on_click: Callable[[str], Any] | None = None,
    on_double_click: Callable[[str], Any] | None = None,
    template: bool = False,
) -> None:
    """Pone (o reemplaza) la bandeja del sistema. Segura desde cualquier hilo.

    `icon`: ruta (`str` o `Path`) o bytes de un PNG/SVG. `menu`: la descripción
    de `aurora.menus`. `on_click`/`on_double_click` reciben `"left"`, `"right"`
    o `"middle"`.
    """

def tray_hide() -> None:
    """Quita la bandeja del sistema. Segura desde cualquier hilo."""

def notify(
    summary: str,
    body: str = "",
    icon: str | PathLike[str] | None = None,
    app_id: str | None = None,
) -> None:
    """Muestra una notificación del sistema. Segura desde cualquier hilo.

    Sin bucle en marcha se envía en el hilo que llama; si el sistema no las
    admite, se avisa por stderr. En Windows, `app_id` es el AUMID de la app:
    sin él el aviso lo firma la identidad de reserva de PowerShell.
    """

def app_id_set(app_id: str) -> None:
    """Fija la identidad (AUMID) de la app en el proceso. Fuera de Windows, no-op."""

def app_id_register(
    app_id: str,
    name: str,
    target: str | PathLike[str],
    arguments: str | None = None,
) -> bool:
    """Registra la identidad con un acceso directo del menú Inicio (Windows).

    Crea (o actualiza) `%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\<name>.lnk`
    apuntando a `target` con `app_id`. Devuelve `False` fuera de Windows; los
    fallos también devuelven `False` y el motivo va por stderr.
    """

def inspection() -> dict[str, Any] | None:
    """Estado del inspector de la app que construye la vista o ejecuta un manejador:
    `open`, `pick`, `selected`, `hovered`, `rect` (caja del nodo elegido) y `frames` (coste
    de los últimos frames, solo con el panel abierto). `None` si no hay app con inspector."""

def inspect_open(open: bool) -> None:
    """Abre o cierra el panel del inspector. `RuntimeError` fuera de la vista o un manejador."""

def inspect_pick(pick: bool) -> None:
    """Entra o sale del modo selección (entrar abre el panel)."""

def inspect_select(key: str | None) -> None:
    """Elige el nodo `key` en el inspector (o ninguno)."""

def inspect_reveal(key: str, top: float, bottom: float) -> None:
    """Tras el próximo layout, desplaza el `scroll` `key` para mostrar esa franja de su contenido."""

class KeyEvent:
    """Evento de teclado que reciben los manejadores `on_key`."""

    key: str
    text: str | None
    ctrl: bool
    shift: bool
    alt: bool
    meta: bool
    repeat: bool
    def matches(self, combo: str) -> bool:
        """`True` si la pulsación es exactamente `combo` (`"ctrl+s"`, `"mod+k"`, `"shift+tab"`)."""

class ScrollEvent:
    """Evento que reciben los manejadores `on_scroll`: desplazamiento y zona visible (px lógicos)."""

    x: float
    y: float
    width: float
    height: float

class DragEvent:
    """Evento que reciben los manejadores `on_drag`: posición del puntero, desplazamiento
    desde donde se pulsó (px lógicos) y fase del gesto (`"start"`, `"move"` o `"end"`)."""

    x: float
    y: float
    dx: float
    dy: float
    phase: str

class Pilot:
    """Ejecuta una app sin ventana y simula el puntero frame a frame (para tests).

    Usa el mismo runtime que la ventana: hit-testing, burbujeo, capas y reconstrucción.
    Las coordenadas están en píxeles lógicos. Cada acción avanza un frame.
    """

    def __init__(
        self,
        build: Callable[[], dict[str, Any]],
        width: float = 960.0,
        height: float = 640.0,
        scale: float = 1.0,
        inspector: bool = False,
    ) -> None: ...
    def frame(self, dt: float = 1 / 60) -> bool:
        """Avanza un frame. Devuelve `True` si quedan transiciones en curso."""
    def settle(self, max_frames: int = 600) -> None:
        """Avanza frames hasta que terminen todas las transiciones."""
    def move_to(self, x: float, y: float) -> None: ...
    def leave(self) -> None:
        """Saca el puntero de la ventana."""
    def mouse_down(self) -> None: ...
    def mouse_up(self) -> None: ...
    def click_at(self, x: float, y: float) -> None: ...
    def drag(self, key: str, dx: float = 0.0, dy: float = 0.0, steps: int = 4) -> None:
        """Arrastra desde el centro de `key` desplazando `(dx, dy)` en `steps` movimientos, y suelta."""
    @property
    def cursor(self) -> str:
        """Cursor del ratón (`"default"`, `"pointer"`, `"text"`, `"grab"`, `"grabbing"`,
        `"col-resize"`, `"row-resize"` o `"crosshair"`)."""
    def click(self, key: str) -> None:
        """Clic en el centro del nodo `key`. `LookupError` si no se pintó."""
    def rect(self, key: str) -> tuple[float, float, float, float] | None:
        """`(x, y, ancho, alto)` del nodo en el último frame."""
    def wheel(self, dy: float = 0.0, dx: float = 0.0, lines: bool = False) -> None:
        """Rueda bajo el puntero. Positivo = hacia el final. `lines=True`: pasos de rueda animados."""
    def scroll(self, key: str, dy: float = 0.0, dx: float = 0.0) -> None:
        """Mueve el puntero al centro de `key` y desplaza esos píxeles."""
    def scroll_offset(self, key: str) -> tuple[float, float] | None:
        """`(x, y)` desplazados del contenedor `scroll` con esa key."""
    def chart_view(self, key: str) -> tuple[float, float] | None:
        """Ventana visible del eje x del `chart` con esa key (sin zoom, su dominio)."""
    def press(self, combo: str) -> None:
        """Pulsa y suelta una tecla o combinación (`"tab"`, `"shift+tab"`, `"ctrl+s"`)."""
    def key_down(self, combo: str) -> None: ...
    def key_up(self, combo: str) -> None: ...
    def type(self, text: str) -> None:
        """Escribe texto en el campo enfocado, como desde el teclado (`\\n` = Enter)."""
    def ime_preedit(self, text: str) -> None:
        """Simula la composición de un IME (texto sin confirmar; vacío la cancela)."""
    def ime_commit(self, text: str) -> None:
        """Simula que el IME confirma texto."""
    def selection(self, key: str) -> tuple[int, int] | None:
        """Selección del campo `key` en caracteres; `(n, n)` si solo hay cursor."""
    clipboard: str
    """Portapapeles del piloto (en memoria)."""
    def focus(self, key: str) -> None:
        """Enfoca `key` como con el teclado. `LookupError` si no es enfocable."""
    @property
    def tooltip(self) -> str | None:
        """Texto del tooltip visible."""
    @property
    def focused(self) -> str | None:
        """Key del nodo enfocado."""
    @property
    def stats(self) -> dict[str, Any]:
        """Coste del último frame en ms (`build`, `parse`, `style`, `layout`, `draw`
        —los `canvas` y los `chart`—, `paint` y `total`, su suma), `nodes`,
        `rebuilt`, `layout_cached` (si se reutilizó el layout del frame anterior) y `damage`
        (zona repintada `(x, y, ancho, alto)`, o `None` si no se pintó nada)."""
    @property
    def hovered(self) -> str | None:
        """Key del nodo interactivo bajo el puntero."""
    @property
    def inspection(self) -> dict[str, Any] | None:
        """Estado del inspector (como `inspection()`), o `None` si se creó sin inspector."""
    def resize(self, width: float, height: float) -> None: ...
    def png(self, path: str) -> None:
        """Guarda el último frame como PNG."""
