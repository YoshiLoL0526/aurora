"""Componentes con estilo por defecto, construidos solo con primitivas.

Casi ningún componente necesita código nativo: el núcleo Rust sabe pintar
cajas, texto, sombras y gradientes, animar estados hover/pressed y editar texto
(el nodo `input`). Todo lo demás se compone aquí, en Python.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable, Hashable, Mapping, Sequence
from typing import Any, Literal, TypeVar

from . import _motion as motion
from . import animate
from .elements import Element, TextLike, box, column, image, row, scroll, spacer, text
from .signal import Signal

T = TypeVar("T", bound=Hashable)
Options = Sequence[T] | Sequence[tuple[T, str]]

Variant = Literal["primary", "soft", "ghost"]

_BUTTON_VARIANTS: dict[str, dict[str, Any]] = {
    "primary": dict(
        bg="$primary",
        bg_hover="$primary_hover",
        bg_pressed="$primary_pressed",
        color="#FFFFFF",
        shadow=(0, 6, 18, "$glow"),
    ),
    "soft": dict(
        bg="$surface_hover",
        bg_hover="$surface_pressed",
        bg_pressed="$border",
        color="$text",
        border_width=1,
        border_color="$border",
    ),
    "ghost": dict(
        bg="#00000000",
        bg_hover="$surface_hover",
        bg_pressed="$surface_pressed",
        color="$muted",
    ),
}


def button(
    label: TextLike,
    on_click: Callable[[], Any] | None = None,
    *,
    variant: Variant = "primary",
    key: str | None = None,
    **style: Any,
) -> Element:
    styles = {
        **_BUTTON_VARIANTS[variant],
        "padding": (10, 18),
        "radius": "$md",
        "align": "center",
        "justify": "center",
        "press_scale": 0.96,
        "font_weight": 600,
        **style,
    }
    return box(on_click=on_click, key=key, **styles)[text(label)]


def card(**style: Any) -> Element:
    return column(
        **{
            "bg": "$surface",
            "radius": "$lg",
            "padding": 20,
            "gap": 12,
            "border_width": 1,
            "border_color": "$border",
            "shadow": (0, 10, 30, "$shadow"),
            **style,
        }
    )


def badge(label: TextLike, *, tone: str = "accent") -> Element:
    return row(padding=(4, 10), radius="$full", bg=f"${tone}", align="center")[
        text(label, size=11, weight=700, color="#0B0D14", letter_spacing=0.4)
    ]


def stat(label: str, value: TextLike, delta: str | None = None, *, positive: bool = True) -> Element:
    """Tarjeta de métrica para dashboards."""
    return card(grow=1, gap=6)[
        text(label, size=12, weight=500, color="$muted", letter_spacing=0.3),
        row(gap=10, align="baseline")[
            text(value, size=28, weight=700),
            delta and text(delta, size=13, weight=600, color="$success" if positive else "$danger"),
        ],
    ]


def progress(
    value: Signal[float] | float,
    *,
    max: float = 1.0,
    color: str | tuple[str, str, float] = "$primary",
    **style: Any,
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
    return box(**{"height": 8, "radius": "$full", "bg": "$surface_hover", **style})[
        box(width=f"{ratio * 100:.4f}%", height="100%", radius="$full", animate_layout=motion.move(), **fill)
    ]


def spinner(
    *, size: float = 8, gap: float = 5, tone: str = "$primary", key: str | None = None, **style: Any
) -> Element:
    """Indicador de carga: tres puntos que laten en cadena (vaivén perpetuo).

    Mientras está visible no hay reposo — la app sigue pintando frames, que es
    lo que necesita un indicador de carga — y `pilot.settle()` no lo detiene.
    Con `App(motion=False)` queda fijo, a opacidad plena.
    """
    return row(key=key, gap=gap, align="center", **style)[
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
    **style: Any,
) -> Element:
    """Marcador de carga: bloques grises con la forma del contenido que llega.

    Con varias `lines`, la última queda más corta, como el final de un párrafo.
    Late despacio mientras está visible (con `App(motion=False)`, fijo). Los
    `estilo` van a cada bloque (`bg`, `radius`, `width`…).
    """
    base = {"bg": "$surface_hover", "radius": "$sm", "pulse": motion.pulse(1.6, floor=0.55), **style}
    if lines <= 1:
        return box(**{"width": width, "height": height, **base})
    last = "60%" if isinstance(width, str) else width * 0.6
    return column(gap=gap)[
        [box(**{"width": width, "height": height, **base}) for _ in range(lines - 1)],
        box(**{"width": last, "height": height, **base}),
    ]


_INPUT_STYLE: dict[str, Any] = dict(
    bg="$surface",
    border_width=1,
    border_color="$border",
    radius="$md",
    padding=(9, 12),
)


def _field(
    value: Signal[str] | TextLike,
    on_change: Callable[[str], Any] | None,
    on_submit: Callable[[str], Any] | None,
    key: str | None,
    style: dict[str, Any],
) -> Element:
    if isinstance(value, Signal):
        signal = value

        def change(text: str) -> None:
            signal.set(text)
            if on_change is not None:
                on_change(text)

        handler: Callable[[str], Any] | None = change
    else:
        handler = on_change
    return Element(
        "input",
        content=value,
        key=key,
        on_change=handler,
        on_submit=on_submit,
        **{**_INPUT_STYLE, **style},
    )


def text_input(
    value: Signal[str] | TextLike,
    *,
    placeholder: str = "",
    on_change: Callable[[str], Any] | None = None,
    on_submit: Callable[[str], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Campo de texto de una línea.

    Con un `Signal[str]` queda enlazado en los dos sentidos: lo que se escribe
    actualiza el Signal y lo que se asigna al Signal aparece en el campo.
    `on_submit(texto)` se llama al pulsar Enter.
    """
    return _field(value, on_change, on_submit, key, {"placeholder": placeholder, **style})


def textarea(
    value: Signal[str] | TextLike,
    *,
    placeholder: str = "",
    rows: int = 3,
    on_change: Callable[[str], Any] | None = None,
    on_submit: Callable[[str], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Campo de texto multilínea. Crece con el contenido (mínimo `rows` líneas).

    Enter inserta un salto de línea; Ctrl+Enter (Cmd+Enter en macOS) llama a
    `on_submit(texto)`.
    """
    styles = {"placeholder": placeholder, "multiline": True, "rows": rows, "padding": (10, 12), **style}
    return _field(value, on_change, on_submit, key, styles)


# --- Utilidades -------------------------------------------------------------

# Iconos vectoriales: nítidos a cualquier tamaño y densidad de pantalla.
_CHECK = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none" stroke="#FFFFFF" '
    b'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 8.5l3 3 6-7"/></svg>'
)
_CHEVRON = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none" stroke="#8A91A8" '
    b'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6l4 4 4-4"/></svg>'
)


def _toggle(
    state: Signal[bool] | bool, on_change: Callable[[bool], Any] | None
) -> tuple[bool, Callable[[], None]]:
    """Valor actual y acción de alternarlo, para controles enlazados a un `Signal[bool]`."""
    current = state() if isinstance(state, Signal) else bool(state)

    def flip() -> None:
        value = not current
        if isinstance(state, Signal):
            state.set(value)
        if on_change is not None:
            on_change(value)

    return current, flip


def _items(options: Options) -> list[tuple[Any, str]]:
    return [o if isinstance(o, tuple) else (o, str(o)) for o in options]


def _has_autofocus(element: Element) -> bool:
    """Si algún nodo del subárbol pide el foco al aparecer (para no quitárselo)."""
    return bool(element.style.get("autofocus")) or any(_has_autofocus(c) for c in element.children)


def field(
    control: Element,
    *,
    label: str | None = None,
    hint: str | None = None,
    error: str | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Campo de formulario: etiqueta, control y mensaje de ayuda o error.

    `error` sustituye a `hint` en color de peligro (`$danger`): pásalo con el
    texto del problema y quítalo cuando el valor sea válido. Los `estilo` van a
    la columna (`gap`, `width`, `grow`…).
    """
    message = error if error else hint
    return column(**{"gap": 6, "key": key, **style})[
        label is not None and text(label, size=12, weight=600),
        control,
        message is not None and text(message, size=11, color="$danger" if error else "$muted"),
    ]


# --- Componentes ------------------------------------------------------------


def divider(*, vertical: bool = False, color: str = "$border", **style: Any) -> Element:
    """Línea separadora de 1 px. Horizontal por defecto; `vertical=True` en una `row`."""
    size = {"width": 1} if vertical else {"height": 1}
    return box(**{**size, "bg": color, "shrink": 0, **style})


_AVATAR_TONES = ("$primary", "$accent", "$success", "$muted")


def avatar(
    name: str = "",
    *,
    src: str | os.PathLike[str] | bytes | None = None,
    size: float = 32,
    **style: Any,
) -> Element:
    """Avatar circular: la imagen `src` recortada, o las iniciales de `name` sobre un
    color estable (el mismo nombre siempre da el mismo color)."""
    shape = {"width": size, "height": size, "radius": "$full", "shrink": 0}
    if src is not None:
        return image(src, fit="cover", **{**shape, **style})
    initials = "".join(word[0] for word in name.split()[:2]).upper() or "?"
    tone = _AVATAR_TONES[sum(map(ord, name)) % len(_AVATAR_TONES)]
    return box(**{**shape, "bg": tone, "align": "center", "justify": "center", **style})[
        text(initials, size=size * 0.38, weight=700, color="#FFFFFF")
    ]


def tooltip(child: Element, tip: str) -> Element:
    """Muestra `tip` al dejar el puntero medio segundo sobre `child`.

    Equivale a pasar `tooltip="..."` a cualquier elemento.
    """
    child.style["tooltip"] = tip
    return child


def menu(
    trigger: Element,
    items: Sequence[tuple[str, Callable[[], Any]] | tuple[str, Callable[[], Any], dict[str, Any]]],
    *,
    key: str,
    drop: float = 44,
    **style: Any,
) -> Element:
    """Menú de acciones: `trigger` (el elemento que se pulsa) abre una lista.

    Cada opción es `(etiqueta, on_click)` o `(etiqueta, on_click, estilo)` — el
    estilo extra va al texto, para una acción peligrosa: `{"color": "$danger"}`.
    La lista se pinta por encima (`layer="overlay"`), entra deslizándose y se
    cierra al elegir, al hacer clic fuera o con Esc. `drop` es la distancia del
    panel al borde superior del disparador, y `key` (obligatoria, como en
    `virtual_list`) guarda el estado de abierto. Las opciones tienen la key
    `f"{key}-item-{índice}"`.
    """
    items = list(items)
    open_ = _OPEN.setdefault(key, Signal(False))

    def close() -> None:
        open_.set(False)

    def toggle() -> None:
        open_.set(not open_())

    def on_key(e: Any) -> bool | None:
        if e.matches("escape") and open_():
            close()
            return True
        return None

    def option(i: int, entry: Sequence[Any]) -> Element:
        label, action = entry[0], entry[1]
        extra: dict[str, Any] = entry[2] if len(entry) > 2 else {}
        return row(
            key=f"{key}-item-{i}",
            padding=(8, 12),
            radius=8,
            bg_hover="$surface_hover",
            on_click=lambda a=action: (close(), a()),
        )[text(label, size=13, **extra)]

    # El clic del disparador abre y cierra la lista (es su única acción).
    trigger.handlers["click"] = toggle
    panel = open_() and [
        # Fondo invisible que cierra al hacer clic fuera.
        box(
            layer="overlay",
            position="absolute",
            left=-10_000,
            top=-10_000,
            width=20_000,
            height=20_000,
            focusable=False,
            on_click=close,
        ),
        box(
            layer="overlay",
            position="absolute",
            top=drop,
            left=0,
            min_width=180,
            padding=4,
            radius="$md",
            bg="$surface",
            border_width=1,
            border_color="$border",
            shadow=(0, 12, 32, "$shadow"),
            enter=motion.entering(animate.slide(y=-6)),
            exit=motion.leaving(animate.fade()),
        )[column(gap=2)[[option(i, entry) for i, entry in enumerate(items)]]],
    ]
    return column(**{"key": key, "on_key": on_key, **style})[trigger, panel]


def accordion(
    sections: Sequence[tuple[Any, str, Element]],
    open: Signal[Any],
    *,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Acordeón: cada sección se despliega al pulsar su cabecera.

    `sections` son triples `(valor, título, contenido)` y `open` el `Signal` con
    la sección desplegada (`None` con todas plegadas; pulsar la cabecera de la
    abierta la pliega). El contenido se despliega con la altura animada y
    `overflow="hidden"`, se queda montado al plegarse (conserva su estado) y no
    recibe clics mientras está oculto. Cada sección tiene la key
    `f"{key}-{valor}"`.
    """
    base = key or f"accordion-{id(open)}"

    def section(value: Any, title: str, content: Element) -> Element:
        shown = open() == value
        # El contenido no se encoge al plegarse: se recorta, no se aplasta.
        content.style.setdefault("shrink", 0)
        return column(key=f"{base}-{value}", gap=0)[
            row(
                padding=(10, 12),
                radius="$md",
                align="center",
                bg_hover="$surface_hover",
                on_click=lambda v=value, on=shown: open.set(None if on else v),
            )[
                text(title, size=14, weight=600),
                spacer(),
                text("▾" if shown else "▸", size=12, color="$muted"),
            ],
            box(
                overflow="hidden",
                animate_layout=motion.move(),
                height=None if shown else 0,
            )[content],
        ]

    return column(**{"gap": 4, **style})[[section(v, t, c) for v, t, c in sections]]


def dialog(
    open: Signal[bool] | bool,
    content: Element,
    *,
    title: TextLike | None = None,
    on_close: Callable[[], Any] | None = None,
    width: float = 420,
    key: str | None = None,
    **style: Any,
) -> Element | None:
    """Diálogo modal: fondo oscurecido, tarjeta centrada y cierre al hacer clic
    fuera o con Esc. Se muestra cuando `open` es verdadero.

    Con un `Signal[bool]`, se cierra solo (el clic de fuera y Esc lo ponen a
    `False`); si `open` es un booleano fijo, usa `on_close` para actualizar el
    estado tú (`on_close=lambda: modal.set(None)` sirve también para modales de
    varios estados). `title` añade un encabezado; los `estilo` van a la tarjeta
    (`padding`, `shadow`…).

    La tarjeta toma el foco al abrirse y lo atrapa (Tab no sale de ella), salvo
    que el contenido traiga un `autofocus`, que gana. Entra con un zoom suave y
    sale fundiéndose, como el resto de los componentes. Colócalo como último
    hijo de la raíz (o con `layer="overlay"`) para que quede por encima.
    """
    if not (open() if isinstance(open, Signal) else open):
        return None

    def close() -> None:
        if isinstance(open, Signal):
            open.set(False)
        if on_close is not None:
            on_close()

    def on_key(e: Any) -> bool | None:
        if e.matches("escape"):
            close()
            return True
        return None

    card_styles: dict[str, Any] = {
        "width": width,
        "padding": 24,
        "gap": 16,
        "capture": True,
        "focusable": True,
        "enter": motion.entering(animate.zoom(0.96)),
        **style,
    }
    if not _has_autofocus(content):
        card_styles["autofocus"] = True
    return box(
        key=key,
        position="absolute",
        top=0,
        left=0,
        right=0,
        bottom=0,
        bg="#000000AA",
        align="center",
        justify="center",
        enter=motion.entering(animate.fade()),
        exit=motion.leaving(animate.fade()),
        on_click=close,
        on_key=on_key,
    )[card(**card_styles)[title is not None and text(title, size=17, weight=700), content]]


def toast(
    message: Signal[str | None] | TextLike | None,
    *,
    on_close: Callable[[], Any] | None = None,
    tone: str = "$accent",
    key: str | None = None,
    **style: Any,
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
        **style,
    )[
        box(width=8, height=8, radius="$full", bg=tone, shrink=0),
        text(message, size=13, shrink=1, max_lines=2),
        text("✕", size=12, color="$muted"),
    ]


def checkbox(
    checked: Signal[bool] | bool,
    label: TextLike | None = None,
    *,
    on_change: Callable[[bool], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Casilla de verificación. Con un `Signal[bool]` se enlaza sola; `on_change(valor)`
    se llama en cada cambio. Se activa con clic, Enter o Espacio.

    La caja funde su color y la marca entra encogiéndose; con `App(motion=False)`
    (o `AURORA_MOTION=0`) el cambio es inmediato.
    """
    on, flip = _toggle(checked, on_change)
    mark = box(
        width=18,
        height=18,
        radius=5,
        align="center",
        justify="center",
        shrink=0,
        bg="$primary" if on else "$surface",
        border_width=1.5,
        border_color="$primary" if on else "$muted",
        transition=motion.fast(),
    )[
        on
        and image(
            _CHECK,
            width=12,
            enter=motion.entering(animate.zoom(0.55)),
            exit=motion.leaving(animate.zoom(0.55)),
        )
    ]
    return row(**{"gap": 8, "align": "center", "radius": 6, "key": key, "on_click": flip, **style})[
        mark, label is not None and text(label)
    ]


def switch(
    on: Signal[bool] | bool,
    label: TextLike | None = None,
    *,
    on_change: Callable[[bool], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Interruptor encendido/apagado. Igual que `checkbox`, con otra forma.

    El knob se desliza y el fondo funde su color al cambiar; con `App(motion=False)`
    (o `AURORA_MOTION=0`) el cambio es inmediato.
    """
    value, flip = _toggle(on, on_change)
    track = box(
        width=36,
        height=20,
        radius="$full",
        shrink=0,
        bg="$primary" if value else "$border",
        transition=motion.fast(),
    )[
        box(
            position="absolute",
            top=2,
            left=18 if value else 2,
            width=16,
            height=16,
            radius="$full",
            bg="#FFFFFF",
            shadow=(0, 1, 3, "#00000040"),
            animate_layout=motion.move(),
        )
    ]
    return row(**{"gap": 10, "align": "center", "radius": 10, "key": key, "on_click": flip, **style})[
        track, label is not None and text(label)
    ]


def radio(options: Options, selected: Signal[Any], *, key: str | None = None, **style: Any) -> Element:
    """Grupo de botones de opción: uno activo a la vez.

    `options` son valores (o pares `(valor, etiqueta)`) y `selected`, el `Signal`
    con el valor activo. Cada fila (círculo y etiqueta) se activa con clic, Enter
    o Espacio y tiene la key `f"{key}-{valor}"`. El punto interior entra
    encogiéndose, como la marca de un `checkbox`.
    """
    items = _items(options)
    base = key or f"radio-{id(selected)}"

    def option(value: Any, label: str) -> Element:
        on = selected() == value
        circle = box(
            width=18,
            height=18,
            radius="$full",
            align="center",
            justify="center",
            shrink=0,
            bg="$primary" if on else "$surface",
            border_width=1.5,
            border_color="$primary" if on else "$muted",
            transition=motion.fast(),
        )[
            on
            and box(
                width=7,
                height=7,
                radius="$full",
                bg="#FFFFFF",
                enter=motion.entering(animate.zoom(0.4)),
                exit=motion.leaving(animate.zoom(0.4)),
            )
        ]
        return row(
            key=f"{base}-{value}",
            gap=8,
            align="center",
            radius=6,
            on_click=lambda v=value: selected.set(v),
        )[circle, text(label, transition=motion.fast())]

    return column(**{"gap": 10, **style})[[option(v, label) for v, label in items]]


def segmented(
    options: Options, selected: Signal[Any], *, width: float = 220, key: str | None = None, **style: Any
) -> Element:
    """Selector segmentado: un pulgar se desliza hasta la opción activa.

    `options` son valores (o pares `(valor, etiqueta)`) y `selected`, el `Signal`
    con el valor activo. Las ranuras miden todas lo mismo (de ahí el `width`, en
    píxeles: es lo que permite que el pulgar se ancle por fracción). Cada opción
    tiene la key `f"{key}-{valor}"` y el pulgar la suya, `f"{key}-thumb"`. Los
    `estilo` van al contenedor.
    """
    items = _items(options)
    values = [v for v, _ in items]
    base = key or f"segmented-{id(selected)}"
    n = max(1, len(items))
    index = values.index(selected()) if selected() in values else 0

    def option(value: Any, label: str) -> Element:
        on = selected() == value
        return box(
            key=f"{base}-{value}",
            grow=1,
            width=0,
            padding=(6, 12),
            radius=9,
            align="center",
            justify="center",
            bg_hover=None if on else "$surface_pressed",
            on_click=lambda v=value: selected.set(v),
        )[
            text(
                label,
                size=12,
                weight=600,
                color="$text" if on else "$muted",
                max_lines=1,
                transition=motion.fast(),
            )
        ]

    return row(**{"padding": 3, "radius": "$md", "bg": "$surface_hover", "width": width, **style})[
        box(grow=1, width=0)[
            # El pulgar, primero: se pinta debajo de las etiquetas.
            box(
                key=f"{base}-thumb",
                position="absolute",
                left=f"{index * 100 / n:.4f}%",
                top=0,
                bottom=0,
                width=f"{100 / n:.4f}%",
                radius=9,
                bg="$surface",
                shadow=(0, 1, 4, "$shadow"),
                animate_layout=motion.move(),
            ),
            row()[[option(v, label) for v, label in items]],
        ],
    ]


# Valor con el que empezó el arrastre de cada `slider`, por key: el estado de los
# componentes no sobrevive a las reconstrucciones, así que vive aquí.
_DRAG_START: dict[str, float] = {}


def slider(
    value: Signal[float],
    *,
    min: float = 0.0,
    max: float = 1.0,
    width: float = 180,
    on_change: Callable[[float], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Deslizador horizontal: arrastra el pulgar para cambiar `value`.

    `value` va de `min` a `max` y se recorta a ese rango; `width` fija el ancho
    en píxeles (el arrastre se calcula con él: no lo pongas en `%`).
    `on_change(valor)` se llama en cada paso del arrastre. El pulgar y el
    relleno siguen el valor con el movimiento común (con `App(motion=False)`, al
    instante).
    """
    if max <= min:
        raise ValueError("max debe ser mayor que min")
    low, high = float(min), float(max)
    current = float(value())
    current = low if current < low else high if current > high else current
    span = high - low
    t = (current - low) / span
    travel = float(width) - 16.0
    k = key or f"slider-{id(value)}"

    def set_value(v: float) -> None:
        v = low if v < low else high if v > high else v
        value.set(v)
        if on_change is not None:
            on_change(v)

    def on_drag(e: Any) -> None:
        if e.phase == "start":
            _DRAG_START[k] = float(value())
            return
        start = _DRAG_START.get(k)
        if start is None:
            return
        set_value(start + e.dx / travel * span)
        if e.phase == "end":
            _DRAG_START.pop(k, None)

    fill = box(
        position="absolute",
        left=0,
        top=0,
        bottom=0,
        width=f"{t * 100:.4f}%",
        radius="$full",
        bg="$primary",
        animate_layout=motion.move(),
    )
    # Punto de anclaje sin ancho: su centro viaja por el carril y el pulgar cuelga
    # de él centrado (16 x 16), así no se sale por los extremos.
    anchor = box(
        position="absolute", left=f"{t * 100:.4f}%", top=0, bottom=0, width=0, animate_layout=motion.move()
    )[
        box(
            position="absolute",
            left=-8,
            top=-5,
            width=16,
            height=16,
            radius="$full",
            bg="#FFFFFF",
            border_width=2,
            border_color="$primary",
            shadow=(0, 1, 4, "#00000066"),
        )
    ]
    rail = box(width="100%", height=6, radius="$full", bg="$surface_hover", key=f"{k}-rail")[fill, anchor]
    return box(
        key=key,
        on_drag=on_drag,
        **{
            "width": width,
            "height": 24,
            "padding": (0, 8),
            "justify": "center",
            "cursor": "pointer",
            **style,
        },
    )[rail]


def tabs(options: Options, selected: Signal[Any], *, key: str | None = None, **style: Any) -> Element:
    """Pestañas. `options` son valores (o pares `(valor, etiqueta)`) y `selected` el
    `Signal` con el valor activo. Con una pestaña enfocada, ← y → cambian de pestaña."""
    items = _items(options)
    values = [v for v, _ in items]
    base = key or f"tabs-{id(selected)}"

    def on_key(e: Any) -> bool | None:
        if e.key in ("ArrowLeft", "ArrowRight") and selected() in values:
            step = 1 if e.key == "ArrowRight" else -1
            selected.set(values[(values.index(selected()) + step) % len(values)])
            return True
        return None

    def tab(value: Any, label: str) -> Element:
        active = selected() == value
        return column(
            key=f"{base}-{value}",
            gap=8,
            padding=(8, 12, 0, 12),
            radius=6,
            on_click=lambda: selected.set(value),
        )[
            text(label, weight=600, color="$text" if active else "$muted", transition=motion.fast()),
            box(height=2, radius=1, bg="$primary" if active else "#00000000", transition=motion.fast()),
        ]

    return column(**{"gap": 0, **style})[
        row(gap=4, on_key=on_key)[[tab(v, label) for v, label in items]],
        divider(),
    ]


def pages(
    current: Signal[Any],
    views: Mapping[Any, Callable[[], Element]],
    *,
    key: str = "pages",
    **style: Any,
) -> Element:
    """Una vista por valor de `current`, con transición al cambiar.

    `views` asocia cada valor con una función que devuelve el contenido. Es el
    compañero natural de `tabs` (comparten `Signal`) para cambiar de página: al
    cambiar el valor, la vista nueva entra fundiéndose y la anterior se va.
    Un valor sin vista lanza `ValueError` con las opciones disponibles.

    Cada página es su propio `scroll` — con la key `f"{key}-{valor}"` — que
    ocupa el espacio libre, así que no hacen falta `height`; los `estilo` van a
    él (`padding`, `gap`…). Al volver a una página, empieza arriba: el núcleo
    guarda la posición mientras existe, no entre visitas.
    """
    value = current()
    view = views.get(value)
    if view is None:
        options = ", ".join(repr(v) for v in views)
        raise ValueError(f"pages: no hay vista para {value!r} (usa {options})")
    return scroll(
        key=f"{key}-{value}",
        enter=motion.entering(animate.fade()),
        exit=motion.leaving(animate.fade()),
        **style,
    )[view()]


# Estado abierto/cerrado de cada `select`, por key (los componentes no tienen estado propio).
_OPEN: dict[str, Signal[bool]] = {}
_SELECT_HEIGHT = 40


def select(
    value: Signal[Any],
    options: Options,
    *,
    placeholder: str = "Elegir…",
    key: str | None = None,
    **style: Any,
) -> Element:
    """Desplegable para elegir un valor de `options` (valores o pares `(valor, etiqueta)`).

    La lista se abre por encima del resto (`layer="overlay"`) deslizándose desde el
    desplegable y se cierra al elegir, al hacer clic fuera o con Esc. Con el desplegable
    enfocado, ↑ y ↓ cambian el valor.
    """
    items = _items(options)
    values = [v for v, _ in items]
    k = key or f"select-{id(value)}"
    open_ = _OPEN.setdefault(k, Signal(False))
    current = next((label for v, label in items if v == value()), None)

    def choose(v: Any) -> None:
        value.set(v)
        open_.set(False)

    def on_key(e: Any) -> bool | None:
        if e.key in ("Escape", "Enter") and open_():
            open_.set(False)
            return True
        if e.key in ("ArrowDown", "ArrowUp") and values:
            i = values.index(value()) if value() in values else -1
            step = 1 if e.key == "ArrowDown" else -1
            value.set(values[max(0, min(len(values) - 1, i + step))])
            return True
        return None

    trigger = row(
        key=k,
        height=_SELECT_HEIGHT,
        gap=8,
        align="center",
        padding=(0, 12),
        radius="$md",
        bg="$surface",
        bg_hover="$surface_hover",
        border_width=1,
        border_color="$border",
        on_click=lambda: open_.set(not open_()),
        on_key=on_key,
    )[
        current is not None and text(current, max_lines=1),
        current is None and text(placeholder, color="$muted", max_lines=1),
        spacer(),
        image(_CHEVRON, width=14),
    ]

    def option(i: int, v: Any, label: str) -> Element:
        chosen = v == value()
        return row(
            key=f"{k}-opt-{i}",
            padding=(8, 10),
            radius=8,
            bg="$surface_hover" if chosen else "#00000000",
            bg_hover="$surface_hover",
            on_click=lambda: choose(v),
        )[text(label, weight=600 if chosen else 400, max_lines=1)]

    menu = open_() and [
        # Fondo invisible que cierra al hacer clic fuera.
        box(
            layer="overlay",
            position="absolute",
            left=-10_000,
            top=-10_000,
            width=20_000,
            height=20_000,
            focusable=False,
            on_click=lambda: open_.set(False),
        ),
        box(
            layer="overlay",
            position="absolute",
            top=_SELECT_HEIGHT + 6,
            left=0,
            right=0,
            padding=4,
            radius="$md",
            bg="$surface",
            border_width=1,
            border_color="$border",
            shadow=(0, 12, 32, "$shadow"),
            enter=motion.entering(animate.slide(y=-6)),
            exit=motion.leaving(animate.fade()),
        )[scroll(max_height=240, gap=2)[[option(i, v, label) for i, (v, label) in enumerate(items)]]],
    ]
    return column(**{"min_width": 160, **style})[trigger, menu]


# Zona visible de cada `virtual_list` (desplazamiento y alto), por key.
_VIEWPORTS: dict[str, Signal[tuple[float, float] | None]] = {}
# Alto que se supone visible hasta el primer frame, cuando el núcleo lo mide.
_GUESSED_HEIGHT = 1080.0


def virtual_list(
    count: int,
    item: Callable[[int], Element],
    *,
    item_height: float,
    key: str,
    gap: float = 0,
    overscan: int = 4,
    **style: Any,
) -> Element:
    """Lista desplazable de `count` filas que solo construye las visibles.

    `item(i)` devuelve la fila `i`. Todas las filas miden `item_height` (más `gap`
    entre ellas), así que la lista sabe su alto total y qué filas caen en la zona
    visible sin construirlas: con 100 000 filas, cada reconstrucción crea unas pocas
    decenas. Se reconstruye al desplazarse solo cuando cambia el rango visible;
    `overscan` filas de más por cada lado cubren el desplazamiento entre medias.

    Cada fila ocupa un hueco de todo el ancho y `item_height` de alto: dale `grow=1`
    a su raíz para que lo rellene. `key` es obligatoria: guarda la posición y la zona
    visible. Con `@component`, las filas que siguen visibles no se reconstruyen.
    """
    if item_height <= 0:
        raise ValueError("item_height debe ser positivo")
    viewport = _VIEWPORTS.setdefault(key, Signal(None))
    stride = item_height + gap

    def visible(y: float, height: float) -> tuple[int, int]:
        first = max(0, int(y // stride) - overscan)
        last = min(count, int((y + height) // stride) + 1 + overscan)
        return first, max(first, last)

    def on_scroll(e: Any) -> None:
        current = viewport()
        if current is None or visible(*current) != visible(e.y, e.height):
            viewport.set((e.y, e.height))

    first, last = visible(*(viewport() or (0.0, _GUESSED_HEIGHT)))
    total = count * item_height + max(0, count - 1) * gap
    rows = [
        column(key=f"{key}#{i}", position="absolute", top=i * stride, left=0, right=0, height=item_height)[
            item(i)
        ]
        for i in range(first, last)
    ]
    return scroll(key=key, on_scroll=on_scroll, **style)[box(height=total, shrink=0)[rows]]
