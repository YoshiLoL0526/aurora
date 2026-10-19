"""Selectores con panel: `combobox` (buscar y elegir) y `date_picker` (calendario)."""

from __future__ import annotations

import calendar
import unicodedata
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from .._icons import _CALENDAR, _CHEVRON, _CHEVRON_LEFT, _CHEVRON_RIGHT
from ..elements import Element, box, column, image, row, scroll, spacer, text
from ..signal import Signal
from ._dropdown import backdrop, close_on_key, open_signal, panel
from ._shared import _INPUT_STYLE, Options, _items
from ._state import _ACTIVE, _MONTHS, _QUERIES

_HEIGHT = 40


def _fold(s: str) -> str:
    """Texto para comparar al buscar: sin mayúsculas ni tildes (`"Ávila"` → `"avila"`)."""
    plain = unicodedata.normalize("NFKD", s)
    return "".join(c for c in plain if not unicodedata.combining(c)).casefold()


def combobox(
    value: Signal[Any],
    options: Options,
    *,
    placeholder: str = "Buscar…",
    empty: str = "Sin resultados",
    on_change: Callable[[Any], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Campo con lista filtrable: se escribe para buscar y se elige una opción.

    Como `select`, `options` son valores o pares `(valor, etiqueta)` y `value`
    guarda el valor elegido. Al escribir, la lista se abre con las opciones cuya
    etiqueta contiene el texto (sin distinguir mayúsculas ni tildes); ↑/↓
    recorren las coincidencias, Enter elige la resaltada y Esc cierra sin
    cambiar nada. Al cerrar, el campo vuelve a mostrar la opción elegida.
    `on_change(valor)` se llama al elegir. Las opciones tienen la key
    `f"{key}-opt-{índice}"` (índice en `options`, no en la lista filtrada).
    """
    items = _items(options)
    k = key or f"combobox-{id(value)}"
    open_ = open_signal(k)
    query = _QUERIES.setdefault(k, Signal(None))
    active = _ACTIVE.setdefault(k, Signal(0))
    current = next((label for v, label in items if v == value()), None)

    typed = query()
    needle = _fold(typed or "")
    matches = [(i, v, label) for i, (v, label) in enumerate(items) if needle in _fold(label)]
    highlight = min(active(), len(matches) - 1) if matches else -1

    def close() -> None:
        open_.set(False)
        query.set(None)

    def open_list() -> None:
        if not open_():
            active.set(0)
            open_.set(True)

    def choose(v: Any) -> None:
        close()
        if v != value():
            value.set(v)
            if on_change is not None:
                on_change(v)

    def search(raw: str) -> None:
        query.set(raw)
        active.set(0)
        open_.set(True)

    def on_key(e: Any) -> bool | None:
        if e.key in ("ArrowDown", "ArrowUp"):
            if not open_():
                open_list()
            elif matches:
                step = 1 if e.key == "ArrowDown" else -1
                active.set(max(0, min(len(matches) - 1, highlight + step)))
            return True
        if e.key == "Enter" and open_():
            if highlight >= 0:
                choose(matches[highlight][1])
            else:
                close()
            return True
        if e.key == "Tab" and open_():
            close()  # el foco sigue su camino: la tecla no se consume
            return None
        if open_() and e.matches("escape"):
            close()
            return True
        return None

    field = Element(
        "input",
        content=typed if typed is not None else (current or ""),
        key=f"{k}-field",
        grow=1,
        min_width=0,
        padding=(6, 0),
        placeholder=placeholder,
        on_change=search,
        on_key=on_key,
        role="combobox",
        expanded=open_(),
    )

    def option(i: int, v: Any, label: str, n: int) -> Element:
        chosen = v == value()
        lit = n == highlight
        return row(
            key=f"{k}-opt-{i}",
            padding=(8, 10),
            radius=8,
            role="option",
            selected=chosen,
            label=label,
            position_in_set=n + 1,
            set_size=len(matches),
            bg="$surface_hover" if lit else "#00000000",
            bg_hover="$surface_hover",
            focusable=False,  # el foco se queda en el campo mientras se elige
            on_click=lambda: choose(v),
        )[text(label, weight=600 if chosen else 400, max_lines=1, hidden=True)]

    listing = (
        [option(i, v, label, n) for n, (i, v, label) in enumerate(matches)]
        if matches
        else [text(empty, size=13, color="$muted", padding=(8, 10))]
    )
    opened = open_() and [
        backdrop(close),
        panel(
            top=_HEIGHT + 6,
            right=0,
            content=scroll(max_height=240, gap=2, role="listbox")[listing],
        ),
    ]
    trigger = row(
        **{**_INPUT_STYLE, "padding": (0, 6, 0, 12)},
        height=_HEIGHT,
        gap=6,
        align="center",
        focusable=False,
        on_click=open_list,
    )[
        field,
        box(
            key=f"{k}-toggle",
            padding=6,
            radius=6,
            bg_hover="$surface_hover",
            focusable=False,
            hidden=True,
            on_click=lambda: close() if open_() else open_list(),
        )[image(_CHEVRON, width=14)],
    ]
    return column(**{"key": k, "min_width": 200, **style})[trigger, opened]


_MONTH_NAMES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
_DAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_DAY_INITIALS = "LMXJVSD"


def _short(d: date) -> str:
    """Formato por defecto de `date_picker`: `19 oct 2026`."""
    return f"{d.day} {_MONTH_NAMES[d.month - 1][:3]} {d.year}"


def _long(d: date) -> str:
    """Nombre completo para los lectores de pantalla: `lunes, 19 de octubre de 2026`."""
    return f"{_DAY_NAMES[d.weekday()]}, {d.day} de {_MONTH_NAMES[d.month - 1]} de {d.year}"


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _add_months(d: date, delta: int) -> date:
    year, month = _shift_month(d.year, d.month, delta)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def date_picker(
    value: Signal[date | None] | Signal[date],
    *,
    min: date | None = None,
    max: date | None = None,
    placeholder: str = "Elegir fecha",
    format: Callable[[date], str] = _short,
    first_weekday: int = 0,
    on_change: Callable[[date], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Selector de fecha: un desplegable con el calendario del mes.

    `value` guarda un `datetime.date` (o `None` sin elegir). Las fechas fuera de
    `[min, max]` se ven pero no se pueden elegir. `format` decide cómo se
    muestra la fecha elegida (por defecto `19 oct 2026`) y `first_weekday` el
    primer día de la semana (0 = lunes, 6 = domingo).

    Con el calendario abierto, ←/→ mueven un día, ↑/↓ una semana y RePág/AvPág
    un mes; Enter o Esc lo cierran. El día de hoy va marcado y «Hoy» lo elige.
    Los días tienen la key `f"{key}-day-{fecha.isoformat()}"`.
    """
    if not 0 <= first_weekday <= 6:
        raise ValueError("first_weekday debe ir de 0 (lunes) a 6 (domingo)")
    if min is not None and max is not None and max < min:
        raise ValueError("max debe ser posterior o igual a min")
    k = key or f"date-{id(value)}"
    open_ = open_signal(k)
    today = date.today()
    current = value()

    def clamp(d: date) -> date:
        if min is not None and d < min:
            return min
        if max is not None and d > max:
            return max
        return d

    def allowed(d: date) -> bool:
        return (min is None or d >= min) and (max is None or d <= max)

    shown_month = _MONTHS.setdefault(k, Signal(((current or today).year, (current or today).month)))
    year, month = shown_month()

    def show(d: date) -> None:
        shown_month.set((d.year, d.month))

    def choose(d: date, *, close: bool = True) -> None:
        d = clamp(d)
        show(d)
        if close:
            open_.set(False)
        if d != value():
            value.set(d)
            if on_change is not None:
                on_change(d)

    def flip() -> None:
        if not open_():
            show(clamp(value() or today))
        open_.set(not open_())

    def on_key(e: Any) -> bool | None:
        if close_on_key(e, open_, "escape", "enter"):
            return True
        if not open_():
            return None
        base = value() or clamp(today)
        moves = {
            "ArrowLeft": base - timedelta(days=1),
            "ArrowRight": base + timedelta(days=1),
            "ArrowUp": base - timedelta(days=7),
            "ArrowDown": base + timedelta(days=7),
            "PageUp": _add_months(base, -1),
            "PageDown": _add_months(base, 1),
        }
        if e.key in moves:
            choose(moves[e.key], close=False)
            return True
        return None

    def nav(icon: bytes, delta: int, label: str) -> Element:
        target = _shift_month(year, month, delta)
        last = date(target[0], target[1], calendar.monthrange(*target)[1])
        enabled = (min is None or last >= min) and (max is None or date(*target, 1) <= max)
        return box(
            key=f"{k}-{'prev' if delta < 0 else 'next'}",
            padding=6,
            radius=6,
            opacity=1.0 if enabled else 0.35,
            focusable=False,
            role="button",
            label=label,
            **(
                {"bg_hover": "$surface_hover", "on_click": lambda: shown_month.set(target)} if enabled else {}
            ),
        )[image(icon, width=14)]

    def day(d: date) -> Element:
        inside = d.month == month
        ok = allowed(d)
        chosen = d == current
        styles: dict[str, Any] = {
            "key": f"{k}-day-{d.isoformat()}",
            "width": 34,
            "height": 34,
            "radius": 8,
            "align": "center",
            "justify": "center",
            "focusable": False,
            "role": "gridcell",
            "label": _long(d),
            "selected": chosen,
        }
        if chosen:
            styles["bg"] = "$primary"
        elif d == today:
            styles.update(border_width=1, border_color="$primary")
        if ok:
            styles.update(on_click=lambda: choose(d))
            if not chosen:
                styles["bg_hover"] = "$surface_hover"
        color = "#FFFFFF" if chosen else "$text" if inside else "$muted"
        return box(**styles, opacity=1.0 if ok else 0.3)[
            text(str(d.day), size=13, weight=700 if chosen else 400, color=color, hidden=True)
        ]

    first = date(year, month, 1)
    start = first - timedelta(days=(first.weekday() - first_weekday) % 7)
    weeks = [[start + timedelta(days=w * 7 + i) for i in range(7)] for w in range(6)]
    initials = [_DAY_INITIALS[(first_weekday + i) % 7] for i in range(7)]
    can_today = allowed(today)

    calendar_panel = column(gap=6, padding=6, role="grid", label=f"{_MONTH_NAMES[month - 1]} de {year}")[
        row(align="center")[
            nav(_CHEVRON_LEFT, -1, "Mes anterior"),
            spacer(),
            text(f"{_MONTH_NAMES[month - 1].capitalize()} {year}", size=14, weight=700),
            spacer(),
            nav(_CHEVRON_RIGHT, 1, "Mes siguiente"),
        ],
        row(hidden=True)[
            [
                text(name, size=11, weight=600, color="$muted", width=34, text_align="center")
                for name in initials
            ]
        ],
        column(gap=2)[[row(role="row")[[day(d) for d in week]] for week in weeks]],
        row(justify="end", padding=(4, 0, 0, 0))[
            can_today
            and box(
                key=f"{k}-today",
                padding=(6, 10),
                radius=8,
                bg_hover="$surface_hover",
                focusable=False,
                role="button",
                label="Hoy",
                on_click=lambda: choose(today),
            )[text("Hoy", size=13, weight=600, color="$primary", hidden=True)],
        ],
    ]

    label = format(current) if current is not None else None
    trigger = row(
        **{**_INPUT_STYLE, "padding": (0, 12)},
        key=k,
        height=_HEIGHT,
        gap=8,
        align="center",
        bg_hover="$surface_hover",
        on_click=flip,
        on_key=on_key,
        role="combobox",
        expanded=open_(),
        value=label,
        placeholder=placeholder,
    )[
        image(_CALENDAR, width=16),
        text(label or placeholder, color="$text" if label else "$muted", max_lines=1, hidden=True),
        spacer(),
        image(_CHEVRON, width=14),
    ]
    opened = open_() and [backdrop(lambda: open_.set(False)), panel(top=_HEIGHT + 6, content=calendar_panel)]
    return column(**{"min_width": 180, **style})[trigger, opened]
