"""Selectores con panel: `combobox` (buscar y elegir), `date_picker` (calendario),
`time_picker` (horas del día) y `color_picker` (paleta, tono y saturación)."""

from __future__ import annotations

import builtins
import colorsys
import itertools
import unicodedata
from collections.abc import Callable, Sequence
from datetime import date, time, timedelta
from typing import Any

from .._icons import _CALENDAR, _CHEVRON, _CHEVRON_LEFT, _CHEVRON_RIGHT, _CLOCK
from ..elements import Element, box, column, image, row, scroll, spacer, text
from ..signal import Signal
from ._dropdown import backdrop, close_on_key, open_signal, panel
from ._shared import _INPUT_STYLE, Options, _items
from ._state import _ACTIVE, _DRAFTS, _DRAG_START, _HSV, _MONTHS, _QUERIES

_HEIGHT = 40
# Alto de cada opción de la lista de `time_picker`.
_OPTION = 34


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
    name = style.pop("label", None)  # el nombre lo lleva el campo, que es el que tiene el rol
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
        label=name,
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
            width="100%",
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


def _days_in_month(year: int, month: int) -> int:
    # Sin `calendar`, que alarga el arranque de cualquier app (lo importa `locale`).
    next_year, next_month = _shift_month(year, month, 1)
    return (date(next_year, next_month, 1) - date(year, month, 1)).days


def _add_months(d: date, delta: int) -> date:
    year, month = _shift_month(d.year, d.month, delta)
    return date(year, month, min(d.day, _days_in_month(year, month)))


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
        last = date(target[0], target[1], _days_in_month(*target))
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
    name = style.pop("label", None)  # el nombre lo lleva el disparador, que es el que tiene el rol
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
        label=name,
    )[
        image(_CALENDAR, width=16),
        text(label or placeholder, color="$text" if label else "$muted", max_lines=1, hidden=True),
        spacer(),
        image(_CHEVRON, width=14),
    ]
    opened = open_() and [backdrop(lambda: open_.set(False)), panel(content=calendar_panel)]
    return column(**{"min_width": 180, **style})[trigger, opened]


def _clock(t: time, hour12: bool) -> str:
    """Formato por defecto de `time_picker`: `14:30`, o `2:30 p. m.` con `hour12`."""
    if not hour12:
        return f"{t.hour:02d}:{t.minute:02d}"
    hour = t.hour % 12 or 12
    return f"{hour}:{t.minute:02d} {'a. m.' if t.hour < 12 else 'p. m.'}"


def time_picker(
    value: Signal[time | None] | Signal[time],
    *,
    step: int = 15,
    min: time | None = None,
    max: time | None = None,
    hour12: bool = False,
    placeholder: str = "Elegir hora",
    format: Callable[[time], str] | None = None,
    on_change: Callable[[time], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Selector de hora: un desplegable con las horas del día cada `step` minutos.

    `value` guarda un `datetime.time` (o `None` sin elegir). La lista va de
    `min` a `max` (por defecto, todo el día) y se abre con la hora elegida a la
    vista; una hora que no cae en un paso se muestra igual en el campo. Con
    `hour12` se escribe `2:30 p. m.` en vez de `14:30`; `format` lo decide a
    medida.

    Con la lista abierta, ↑/↓ cambian a la hora anterior o siguiente,
    Inicio/Fin van a la primera y la última, y Enter o Esc la cierran. Las
    opciones tienen la key `f"{key}-{HH:MM}"`.
    """
    if not 1 <= step <= 720:
        raise ValueError("step debe ir de 1 a 720 minutos")
    if min is not None and max is not None and max < min:
        raise ValueError("max debe ser posterior o igual a min")
    k = key or f"time-{id(value)}"
    open_ = open_signal(k)
    current = value()
    show = format or (lambda t: _clock(t, hour12))
    first = min.hour * 60 + min.minute if min is not None else 0
    last = max.hour * 60 + max.minute if max is not None else 24 * 60 - 1
    start = -(-first // step) * step  # el primer paso que no queda antes de `min`
    times = [time(m // 60, m % 60) for m in range(start, last + 1, step)]
    at = times.index(current) if current is not None and current in times else -1

    def choose(t: time, *, close: bool = True) -> None:
        if close:
            open_.set(False)
        if t != value():
            value.set(t)
            if on_change is not None:
                on_change(t)

    def nearest() -> int:
        """La opción de la hora elegida, o la siguiente a ella si no cae en un paso."""
        if current is None:
            return -1
        return next((i for i, t in enumerate(times) if t >= current), len(times) - 1)

    def on_key(e: Any) -> bool | None:
        if close_on_key(e, open_, "escape", "enter"):
            return True
        if not open_() or not times:
            return None
        here = at if at >= 0 else nearest()
        moves = {
            "ArrowDown": here + 1 if here >= 0 else 0,
            "ArrowUp": here - 1 if here >= 0 else 0,
            "Home": 0,
            "End": len(times) - 1,
        }
        if e.key in moves:
            choose(times[builtins.max(0, builtins.min(len(times) - 1, moves[e.key]))], close=False)
            return True
        return None

    def option(i: int, t: time) -> Element:
        chosen = i == at
        return row(
            key=f"{k}-{t.hour:02d}:{t.minute:02d}",
            height=_OPTION,
            shrink=0,
            align="center",
            padding=(0, 10),
            radius=8,
            role="option",
            selected=chosen,
            label=show(t),
            position_in_set=i + 1,
            set_size=len(times),
            bg="$surface_hover" if chosen else "#00000000",
            bg_hover="$surface_hover",
            focusable=False,
            on_click=lambda: choose(t),
        )[text(show(t), size=13, weight=600 if chosen else 400, max_lines=1, hidden=True)]

    focus = at if at >= 0 else nearest()
    gap = 2
    listing = scroll(
        key=f"{k}-list",
        max_height=240,
        gap=gap,
        role="listbox",
        reveal=(focus * (_OPTION + gap), (focus + 1) * (_OPTION + gap)) if focus >= 0 else None,
    )[[option(i, t) for i, t in enumerate(times)]]
    label = show(current) if current is not None else None
    name = style.pop("label", None)  # el nombre lo lleva el disparador, que es el que tiene el rol
    trigger = row(
        **{**_INPUT_STYLE, "padding": (0, 12)},
        key=k,
        height=_HEIGHT,
        gap=8,
        align="center",
        bg_hover="$surface_hover",
        on_click=lambda: open_.set(not open_()),
        on_key=on_key,
        role="combobox",
        expanded=open_(),
        value=label,
        placeholder=placeholder,
        label=name,
    )[
        image(_CLOCK, width=16),
        text(label or placeholder, color="$text" if label else "$muted", max_lines=1, hidden=True),
        spacer(),
        image(_CHEVRON, width=14),
    ]
    opened = open_() and [
        backdrop(lambda: open_.set(False)),
        panel(width="100%", content=listing),
    ]
    return column(**{"min_width": 150, **style})[trigger, opened]


# Paleta por defecto de `color_picker`: tonos que se leen bien sobre fondo claro y oscuro.
_PALETTE = (
    "#EF4444",
    "#F97316",
    "#F59E0B",
    "#EAB308",
    "#84CC16",
    "#22C55E",
    "#10B981",
    "#14B8A6",
    "#06B6D4",
    "#0EA5E9",
    "#3B82F6",
    "#6366F1",
    "#7C5CFF",
    "#A855F7",
    "#D946EF",
    "#EC4899",
    "#F43F5E",
    "#78716C",
    "#64748B",
    "#0F172A",
    "#FFFFFF",
)
# Tonos puros que recorre la franja de tono (de rojo a rojo).
_HUES = ("#FF0000", "#FFFF00", "#00FF00", "#00FFFF", "#0000FF", "#FF00FF", "#FF0000")
_SV_SIZE = (220.0, 132.0)


def _parse_hex(raw: str) -> str | None:
    """`#RGB` o `#RRGGBB` (con o sin `#`) en la forma canónica `#RRGGBB`; `None` si no lo es."""
    s = raw.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6 or any(c not in "0123456789abcdefABCDEF" for c in s):
        return None
    return "#" + s.upper()


def _hsv(hex_color: str) -> tuple[float, float, float]:
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)


def _hex(h: float, s: float, v: float) -> str:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return "#" + "".join(f"{round(c * 255):02X}" for c in (r, g, b))


def color_picker(
    value: Signal[str],
    *,
    palette: Sequence[str] = _PALETTE,
    custom: bool = True,
    on_change: Callable[[str], Any] | None = None,
    key: str | None = None,
    **style: Any,
) -> Element:
    """Selector de color: un desplegable con una paleta, un campo hexadecimal y,
    con `custom`, un cuadro de saturación y brillo con su franja de tono.

    `value` guarda el color como texto `#RRGGBB` (se aceptan `#RGB` y
    minúsculas al escribir, y se guarda en esa forma). `palette` son las
    muestras rápidas; sus keys son `f"{key}-swatch-{índice}"`. El campo
    hexadecimal asigna el color en cuanto el texto es válido.

    El cuadro y la franja se arrastran o se manejan con las flechas cuando
    tienen el foco (en el cuadro, ←/→ cambian la saturación y ↑/↓ el brillo);
    Esc cierra el panel. `on_change(color)` se llama con cada color nuevo.
    """
    k = key or f"color-{id(value)}"
    open_ = open_signal(k)
    draft = _DRAFTS.setdefault(k, Signal(None))
    current = _parse_hex(value() or "") or "#000000"
    # El tono se recuerda aparte: con saturación o brillo a cero, el color no lo conserva.
    hsv = _HSV.setdefault(k, Signal(_hsv(current)))
    h, s, v = hsv()
    if _hex(h, s, v) != current:
        h, s, v = _hsv(current)
        hsv.set((h, s, v))

    def choose(color: str, shade: tuple[float, float, float] | None = None) -> None:
        hsv.set(shade or _hsv(color))
        if color != value():
            value.set(color)
            if on_change is not None:
                on_change(color)

    def paint(nh: float, ns: float, nv: float) -> None:
        shade = (nh % 1.0, min(1.0, max(0.0, ns)), min(1.0, max(0.0, nv)))
        draft.set(None)
        choose(_hex(*shade), shade)

    def typed(raw: str) -> None:
        draft.set(raw)
        color = _parse_hex(raw)
        if color is not None:
            choose(color)

    def settle(*_: Any) -> None:
        draft.set(None)

    def on_key(e: Any) -> bool | None:
        return close_on_key(e, open_, "escape")

    def flip() -> None:
        draft.set(None)
        open_.set(not open_())

    width, height = _SV_SIZE

    def drag_sv(e: Any) -> None:
        if e.phase == "start":
            _DRAG_START[f"{k}-s"], _DRAG_START[f"{k}-v"] = s, v
            return
        if f"{k}-s" not in _DRAG_START:
            return
        paint(h, _DRAG_START[f"{k}-s"] + e.dx / width, _DRAG_START[f"{k}-v"] - e.dy / height)
        if e.phase == "end":
            _DRAG_START.pop(f"{k}-s", None)
            _DRAG_START.pop(f"{k}-v", None)

    def key_sv(e: Any) -> bool | None:
        moves = {
            "ArrowLeft": (-0.05, 0),
            "ArrowRight": (0.05, 0),
            "ArrowUp": (0, 0.05),
            "ArrowDown": (0, -0.05),
        }
        if e.key not in moves:
            return None
        ds, dv = moves[e.key]
        paint(h, s + ds, v + dv)
        return True

    def drag_hue(e: Any) -> None:
        if e.phase == "start":
            _DRAG_START[f"{k}-hue"] = h
            return
        begin = _DRAG_START.get(f"{k}-hue")
        if begin is None:
            return
        paint(min(0.9999, max(0.0, begin + e.dx / width)), s, v)
        if e.phase == "end":
            _DRAG_START.pop(f"{k}-hue", None)

    def key_hue(e: Any) -> bool | None:
        steps = {"ArrowLeft": -1, "ArrowDown": -1, "ArrowRight": 1, "ArrowUp": 1}
        if e.key not in steps:
            return None
        paint(min(0.9999, max(0.0, h + steps[e.key] / 72)), s, v)
        return True

    def thumb(x: float, y: float, color: str) -> Element:
        # Punto de anclaje sin tamaño del que cuelga el círculo centrado.
        return box(position="absolute", left=x, top=y, width=0, height=0)[
            box(
                position="absolute",
                left=-7,
                top=-7,
                width=14,
                height=14,
                radius="$full",
                bg=color,
                border_width=2,
                border_color="#FFFFFF",
                shadow=(0, 1, 4, "#00000080"),
            )
        ]

    picker = (
        custom
        and column(gap=10)[
            box(
                key=f"{k}-sv",
                width=width,
                height=height,
                radius=8,
                gradient=("#FFFFFF", _hex(h, 1, 1), 0),
                cursor="crosshair",
                focusable=True,
                on_drag=drag_sv,
                on_key=key_sv,
                role="slider",
                label="Saturación y brillo",
                value=f"saturación {round(s * 100)} %, brillo {round(v * 100)} %",
            )[
                box(
                    position="absolute",
                    left=0,
                    top=0,
                    right=0,
                    bottom=0,
                    radius=8,
                    gradient=("#00000000", "#000000", 90),
                ),
                thumb(s * width, (1 - v) * height, current),
            ],
            box(
                key=f"{k}-hue",
                width=width,
                height=10,
                direction="row",
                cursor="pointer",
                focusable=True,
                on_drag=drag_hue,
                on_key=key_hue,
                on_value=lambda deg: paint(float(deg) / 360, s, v),
                role="slider",
                label="Tono",
                value=round(h * 360),
                value_min=0,
                value_max=359,
                value_step=5,
            )[
                [box(grow=1, width=0, gradient=(a, b, 0)) for a, b in itertools.pairwise(_HUES)],
                thumb(h * width, 5, _hex(h, 1, 1)),
            ],
        ]
    )

    def swatch(i: int, color: str) -> Element:
        chosen = color.upper() == current
        return box(
            key=f"{k}-swatch-{i}",
            width=24,
            height=24,
            radius=6,
            bg=color,
            border_width=2 if chosen else 1,
            border_color="$text" if chosen else "#80808040",
            focusable=False,
            role="radio",
            checked=chosen,
            label=color.upper(),
            on_click=lambda: (draft.set(None), choose(_parse_hex(color) or current)),
        )

    shown = draft() if draft() is not None else current
    field = Element(
        "input",
        content=shown,
        key=f"{k}-field",
        grow=1,
        min_width=0,
        on_change=typed,
        on_submit=settle,
        on_blur=settle,
        label="Hexadecimal",
        **{**_INPUT_STYLE, "padding": (6, 10)},
    )
    content = column(gap=12, padding=8, width=width + 16, role="dialog", label="Elegir color")[
        picker,
        row(wrap=True, gap=6, role="radiogroup", label="Paleta")[
            [swatch(i, c) for i, c in enumerate(palette)]
        ],
        row(gap=8, align="center")[
            box(width=30, height=30, radius=8, bg=current, border_width=1, border_color="$border", shrink=0),
            field,
        ],
    ]
    trigger = row(
        **{**_INPUT_STYLE, "padding": (0, 12, 0, 8)},
        key=k,
        height=_HEIGHT,
        gap=8,
        align="center",
        bg_hover="$surface_hover",
        on_click=flip,
        on_key=on_key,
        role="combobox",
        expanded=open_(),
        value=current,
        label=style.pop("label", "Color"),
    )[
        box(width=24, height=24, radius=6, bg=current, border_width=1, border_color="#80808040", shrink=0),
        text(current, size=13, max_lines=1, hidden=True),
        spacer(),
        image(_CHEVRON, width=14),
    ]
    opened = open_() and [backdrop(lambda: open_.set(False)), panel(content=content)]
    return column(**{"key": f"{k}-picker", "min_width": 150, "on_key": on_key, **style})[trigger, opened]
