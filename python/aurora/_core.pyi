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
    def press(self, combo: str) -> None:
        """Pulsa y suelta una tecla o combinación (`"tab"`, `"shift+tab"`, `"ctrl+s"`)."""
    def key_down(self, combo: str) -> None: ...
    def key_up(self, combo: str) -> None: ...
    def focus(self, key: str) -> None:
        """Enfoca `key` como con el teclado. `LookupError` si no es enfocable."""
    @property
    def focused(self) -> str | None:
        """Key del nodo enfocado."""
    @property
    def hovered(self) -> str | None:
        """Key del nodo interactivo bajo el puntero."""
    def resize(self, width: float, height: float) -> None: ...
    def png(self, path: str) -> None:
        """Guarda el último frame como PNG."""
