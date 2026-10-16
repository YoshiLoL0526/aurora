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
    backend: str = "auto",
) -> None:
    """Abre una ventana y ejecuta el bucle de eventos hasta que se cierre.

    `backend`: `"auto"`, `"gpu"` o `"cpu"` (`ValueError` con otro valor).
    """

def wake() -> None:
    """Pide reconstruir la vista y despierta el bucle de eventos. Seguro desde cualquier hilo."""

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
        `"col-resize"` o `"row-resize"`)."""
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
        —los `canvas` y los `chart`—, `paint`), `nodes`,
        `rebuilt`, `layout_cached` (si se reutilizó el layout del frame anterior) y `damage`
        (zona repintada `(x, y, ancho, alto)`, o `None` si no se pintó nada)."""
    @property
    def hovered(self) -> str | None:
        """Key del nodo interactivo bajo el puntero."""
    def resize(self, width: float, height: float) -> None: ...
    def png(self, path: str) -> None:
        """Guarda el último frame como PNG."""
