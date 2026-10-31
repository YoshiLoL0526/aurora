"""Superposiciones: menú, diálogo, tooltip y desplegable (`select`)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .. import _motion as motion
from .. import animate
from .._icons import _CHEVRON
from ..elements import Element, TextLike, box, column, image, row, scroll, spacer, text
from ..signal import Signal
from ._dropdown import backdrop, close_on_key, open_signal, panel, toggle
from ._shared import Options, _has_autofocus, _items
from .basic import card

_SELECT_HEIGHT = 40


def menu(
    trigger: Element,
    items: Sequence[tuple[str, Callable[[], Any]] | tuple[str, Callable[[], Any], dict[str, Any]]],
    *,
    key: str,
    drop: float | None = None,
    placement: str = "bottom-start",
    **style: Any,
) -> Element:
    """Menú de acciones: `trigger` (el elemento que se pulsa) abre una lista.

    Cada opción es `(etiqueta, on_click)` o `(etiqueta, on_click, estilo)` — el
    estilo extra va al texto, para una acción peligrosa: `{"color": "$danger"}`.
    La lista se pinta por encima (`layer="overlay"`), entra deslizándose y se
    cierra al elegir, al hacer clic fuera o con Esc. Se coloca debajo del
    disparador (o en el lado de `placement`) y se vuelca si no cabe; `drop` lo
    fija en cambio a esa distancia del borde superior del disparador. `key` (obligatoria, como en
    `virtual_list`) guarda el estado de abierto. Las opciones tienen la key
    `f"{key}-item-{índice}"`.
    """
    items = list(items)
    open_ = open_signal(key)

    def close() -> None:
        open_.set(False)

    def on_key(e: Any) -> bool | None:
        return close_on_key(e, open_, "escape")

    def option(i: int, entry: Sequence[Any]) -> Element:
        label, action = entry[0], entry[1]
        extra: dict[str, Any] = entry[2] if len(entry) > 2 else {}
        return row(
            key=f"{key}-item-{i}",
            padding=(8, 12),
            radius=8,
            role="menuitem",
            label=label,
            position_in_set=i + 1,
            set_size=len(items),
            bg_hover="$surface_hover",
            on_click=lambda a=action: (close(), a()),
        )[text(label, size=13, hidden=True, **extra)]

    # El clic del disparador abre y cierra la lista (es su única acción).
    trigger.handlers["click"] = toggle(open_)
    opened = open_() and [
        backdrop(close),
        panel(
            top=drop,
            placement=placement,
            min_width=180,
            content=column(gap=2, role="menu")[[option(i, entry) for i, entry in enumerate(items)]],
        ),
    ]
    return column(**{"key": key, "on_key": on_key, **style})[trigger, opened]


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

    a11y_card: dict[str, Any] = {"role": "dialog", "modal": True}
    if isinstance(title, str):
        a11y_card["label"] = title
    card_styles: dict[str, Any] = {
        "width": width,
        "padding": 24,
        "gap": 16,
        "capture": True,
        "focusable": True,
        "enter": motion.entering(animate.zoom(0.96)),
        **a11y_card,
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
    )[
        card(**card_styles)[
            title is not None and text(title, size=17, weight=700, hidden="label" in a11y_card),
            content,
        ]
    ]


def tooltip(child: Element, tip: str) -> Element:
    """Muestra `tip` al dejar el puntero medio segundo sobre `child`.

    Equivale a pasar `tooltip="..."` a cualquier elemento.
    """
    child.style["tooltip"] = tip
    return child


def popover(
    trigger: Element,
    content: Element,
    *,
    open: Signal[bool] | None = None,
    placement: str = "bottom-start",
    offset: float = 6,
    label: str | None = None,
    on_close: Callable[[], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Contenido flotante anclado a `trigger`: pulsarlo abre y cierra `content`.

    El panel se pinta por encima del resto (`layer="overlay"`) en el lado de
    `placement` (`"bottom-start"`, `"top"`, `"right-end"`…: un lado y, si se
    quiere, la alineación `start`/`center`/`end`), a `offset` píxeles; si ahí no
    cabe se vuelca al lado opuesto, y nunca se sale de la ventana. Se cierra con
    Esc o al hacer clic fuera, y entonces llama a `on_close()`.

    El estado vive en `open` (un `Signal[bool]`, para abrirlo o cerrarlo desde
    fuera) o, sin él, en la `key`: hace falta una de las dos. Para los lectores
    de pantalla es un `"dialog"` no modal con nombre `label`; toma el foco al
    abrirse (salvo que el contenido traiga un `autofocus`), y el disparador
    anuncia si está desplegado. Los `estilo` van al panel (`width`, `padding`, `gap`…).
    """
    if open is None and key is None:
        raise ValueError("popover necesita una key o un Signal open")
    k = key or f"popover-{id(open)}"
    open_ = open if open is not None else open_signal(k)

    def close() -> None:
        if open_():
            open_.set(False)
            if on_close is not None:
                on_close()

    def on_key(e: Any) -> bool | None:
        if open_() and e.matches("escape"):
            close()
            return True
        return None

    flip = toggle(open_)
    clicked = trigger.handlers.get("click")

    def on_trigger() -> None:
        if open_():
            close()
            return
        if clicked is not None:
            clicked()
        flip()

    trigger.handlers["click"] = on_trigger
    trigger.style["expanded"] = open_()
    shown: dict[str, Any] = {
        "role": "dialog",
        "label": label,
        "padding": 12,
        "min_width": 200,
        "focusable": True,
        **style,
    }
    if not _has_autofocus(content):
        shown.setdefault("autofocus", True)
    opened = open_() and [
        backdrop(close),
        panel(key=f"{k}-panel", placement=placement, offset=offset, content=content, **shown),
    ]
    return column(key=k, on_key=on_key)[trigger, opened]


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
    open_ = open_signal(k)
    current = next((label for v, label in items if v == value()), None)
    name = style.pop("label", None)  # el nombre lo lleva el disparador, que es el que tiene el rol

    def close() -> None:
        open_.set(False)

    def choose(v: Any) -> None:
        value.set(v)
        close()

    def on_key(e: Any) -> bool | None:
        if close_on_key(e, open_, "escape", "enter"):
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
        on_click=toggle(open_),
        on_key=on_key,
        role="combobox",
        expanded=open_(),
        value=current,
        placeholder=placeholder,
        label=name,
    )[
        current is not None and text(current, max_lines=1, hidden=True),
        current is None and text(placeholder, color="$muted", max_lines=1, hidden=True),
        spacer(),
        image(_CHEVRON, width=14),
    ]

    def option(i: int, v: Any, label: str) -> Element:
        chosen = v == value()
        return row(
            key=f"{k}-opt-{i}",
            padding=(8, 10),
            radius=8,
            role="option",
            selected=chosen,
            label=label,
            position_in_set=i + 1,
            set_size=len(items),
            bg="$surface_hover" if chosen else "#00000000",
            bg_hover="$surface_hover",
            on_click=lambda: choose(v),
        )[text(label, weight=600 if chosen else 400, max_lines=1, hidden=True)]

    opened = open_() and [
        backdrop(close),
        panel(
            width="100%",
            content=scroll(max_height=240, gap=2, role="listbox")[
                [option(i, v, label) for i, (v, label) in enumerate(items)]
            ],
        ),
    ]
    return column(**{"min_width": 160, **style})[trigger, opened]
