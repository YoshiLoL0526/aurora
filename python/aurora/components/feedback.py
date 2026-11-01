"""Indicadores de estado y avisos: barra de progreso, spinner, esqueleto y toast."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .. import _motion as motion
from .. import animate
from ..elements import Element, TextLike, box, column, row, text
from ..signal import Signal

if TYPE_CHECKING:
    from typing import Unpack

    from .._style_variants import ProgressStyle, SkeletonStyle, SpinnerStyle, ToastStyle


def progress(
    value: Signal[float] | float,
    *,
    max: float = 1.0,
    color: str | tuple[str, str, float] = "$primary",
    **style: Unpack[ProgressStyle],
) -> Element:
    """Barra de progreso: `value` de 0 a `max` (por defecto, una fracción de 0 a 1).

    Al cambiar el valor la barra crece hasta su nuevo sitio (con
    `App(motion=False)`, de golpe). `color` admite un color del tema o un
    gradiente `(desde, hasta, ángulo)`; los `estilo` van al carril (`height`,
    `width`…).
    """
    if max <= 0:
        raise ValueError("max debe ser positivo")
    current = float(value() if isinstance(value, Signal) else value)
    ratio = current / max
    if not math.isfinite(ratio):
        ratio = 0.0
    ratio = 0.0 if ratio < 0.0 else 1.0 if ratio > 1.0 else ratio
    fill: dict[str, Any] = {"bg": color} if isinstance(color, str) else {"gradient": color}
    track: dict[str, Any] = {
        "height": 8,
        "radius": "$full",
        "bg": "$surface_hover",
        "role": "progressbar",
        "value": current,
        "value_min": 0.0,
        "value_max": float(max),
        **style,
    }
    return box(**track)[
        box(width=f"{ratio * 100:.4f}%", height="100%", radius="$full", animate_layout=motion.move(), **fill)
    ]


def spinner(
    *,
    size: float = 8,
    gap: float = 5,
    tone: str = "$primary",
    key: str | None = None,
    **style: Unpack[SpinnerStyle],
) -> Element:
    """Indicador de carga: tres puntos que laten en cadena (vaivén perpetuo).

    Mientras está visible no hay reposo — la app sigue pintando frames, que es
    lo que necesita un indicador de carga — y `pilot.settle()` no lo detiene.
    Con `App(motion=False)` queda fijo, a opacidad plena.
    """
    props: dict[str, Any] = {"align": "center", "role": "progressbar", **style}
    return row(key=key, gap=gap, **props)[
        [
            box(width=size, height=size, radius="$full", bg=tone, pulse=motion.pulse(delay=i * 0.15))
            for i in range(3)
        ]
    ]


def skeleton(
    *,
    lines: int = 1,
    width: str | float = "100%",
    height: float = 14,
    gap: float = 8,
    **style: Unpack[SkeletonStyle],
) -> Element:
    """Marcador de carga: bloques grises con la forma del contenido que llega.

    Con varias `lines`, la última queda más corta, como el final de un párrafo.
    Late despacio mientras está visible (con `App(motion=False)`, fijo). Los
    `estilo` van a cada bloque (`bg`, `radius`, `width`…).
    """
    # Marcador de carga: decorativo, no se anuncia.
    # `$surface_pressed` y no `$surface_hover`: este casi no se distingue del fondo claro.
    base: dict[str, Any] = {
        "bg": "$surface_pressed",
        "radius": "$sm",
        "pulse": motion.pulse(1.6, floor=0.55),
        "hidden": True,
        **style,
    }
    line: dict[str, Any] = {"width": width, "height": height, **base}
    if lines <= 1:
        return box(**line)
    last: dict[str, Any] = {**line, "width": "60%" if isinstance(width, str) else width * 0.6}
    return column(gap=gap)[[box(**line) for _ in range(lines - 1)], box(**last)]


def toast(
    message: Signal[str | None] | TextLike | None,
    *,
    on_close: Callable[[], Any] | None = None,
    tone: str = "$accent",
    key: str | None = None,
    **style: Unpack[ToastStyle],
) -> Element | None:
    """Aviso flotante (abajo a la derecha). Se muestra si `message` no es `None`.

    Con un `Signal[str | None]`, un clic lo descarta (el Signal pasa a `None`) y
    `on_close` se llama en cada cierre. `tone` es el color del punto de acento;
    los `estilo` van al aviso (`right`, `bottom`, `max_width`…) y su `key` lo
    mantiene estable entre reconstrucciones.

    Entra deslizándose desde abajo y sale fundiéndose. Para que se vaya solo,
    prográmalo con la app: `app.spawn(asyncio.sleep(3))` y pon el Signal a
    `None` al terminar. Colócalo como último hijo de la raíz.
    """
    if message is None or (isinstance(message, Signal) and message() is None):
        return None

    def close() -> None:
        if isinstance(message, Signal):
            message.set(None)
        if on_close is not None:
            on_close()

    props: dict[str, Any] = {"role": "status", "live": "polite", **style}
    return row(
        key=key,
        position="absolute",
        right=24,
        bottom=24,
        max_width=420,
        gap=12,
        align="center",
        padding=(12, 16),
        radius="$md",
        bg="$surface",
        border_width=1,
        border_color="$border",
        shadow=(0, 12, 32, "$shadow"),
        enter=motion.entering(animate.slide(y=8)),
        exit=motion.leaving(animate.fade()),
        on_click=close,
        **props,
    )[
        box(width=8, height=8, radius="$full", bg=tone, shrink=0),
        text(message, size=13, shrink=1, max_lines=2),
        text("✕", size=12, color="$muted", hidden=True),
    ]
