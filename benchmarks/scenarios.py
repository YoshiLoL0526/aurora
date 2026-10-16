"""Escenarios de la suite de benchmarks.

Cada escenario construye una app y una serie de **operaciones**. Cada operación avanza
exactamente un frame del piloto, así que lo que se mide es el coste de un frame real:
reconstrucción (si la hay), layout y pintura. Los datos son deterministas, sin azar ni reloj,
para que dos ejecuciones midan exactamente lo mismo.

`scale` reduce el tamaño de los escenarios (los tests usan escalas pequeñas para que no se
pudran sin pagar su coste).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from aurora import (
    App,
    Pilot,
    Signal,
    badge,
    box,
    card,
    column,
    component,
    row,
    scroll,
    spacer,
    text,
    text_input,
    virtual_list,
)

Op = Callable[[Pilot], None]


@dataclass
class Bench:
    app: App
    ops: dict[str, Op]
    # Se ejecuta una vez, sin medir, tras crear el piloto (p. ej. enfocar un campo).
    setup: Op | None = None
    info: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    make: Callable[[float], Bench]


def _alternate(*steps: Op) -> Op:
    """Operación que alterna entre varias: así cada frame tiene algo que cambiar."""
    i = 0

    def op(pilot: Pilot) -> None:
        nonlocal i
        steps[i % len(steps)](pilot)
        i += 1

    return op


def _idle(pilot: Pilot) -> None:
    pilot.frame()


# --------------------------------------------------------------- lista de 10k ítems


def list_10k(scale: float = 1.0, *, memo: bool = False) -> Bench:
    """Con `memo=True`, cada fila es un `@component`: solo se reconstruyen las dos
    filas cuya selección cambia (la que la pierde y la que la gana)."""
    n = max(10, int(10_000 * scale))
    selected = Signal(0)
    names = [f"Tarea {i:05d} · revisión de {('diseño', 'código', 'datos', 'copy')[i % 4]}" for i in range(n)]

    def item(i: int, on: bool):
        return row(
            key=f"item-{i}",
            gap=12,
            align="center",
            padding=(8, 14),
            radius=8,
            bg="$surface" if on else None,
            bg_hover="$surface",
            on_click=lambda: selected.set(i),
        )[
            box(width=8, height=8, radius=4, bg="$primary" if on else "$border"),
            text(names[i], size=14),
            spacer(),
            text(f"{(i * 37) % 100} %", size=13, color="$muted"),
        ]

    make = component(item) if memo else item

    def view():
        current = selected()
        return column(padding=16, gap=12)[
            text(f"{n} tareas", size=20, weight=700),
            scroll(key="lista", gap=2)[[make(i, i == current) for i in range(n)]],
        ]

    def rebuild(pilot: Pilot) -> None:
        selected.update(lambda s: (s + 1) % n)
        pilot.frame()

    return Bench(
        App(view, size=(960, 640)),
        {
            "rebuild": rebuild,
            "hover": _alternate(lambda p: p.move_to(300, 70), lambda p: p.move_to(300, 110)),
            "scroll": _alternate(lambda p: p.wheel(400), lambda p: p.wheel(-400)),
            "idle": _idle,
        },
        info={"items": n},
    )


# ------------------------------------------------------- lista virtual de 100k filas


def virtual_100k(scale: float = 1.0) -> Bench:
    """100 000 filas en una `virtual_list` con filas `@component`: solo existen las visibles."""
    n = max(10, int(100_000 * scale))
    selected = Signal(0)

    @component
    def item(i: int, on: bool):
        return row(
            key=f"fila-{i}",
            grow=1,
            gap=12,
            align="center",
            padding=(0, 14),
            radius=8,
            bg="$surface" if on else None,
            bg_hover="$surface",
            on_click=lambda: selected.set(i),
        )[
            box(width=8, height=8, radius=4, bg="$primary" if on else "$border"),
            text(f"Tarea {i:06d} · revisión de {('diseño', 'código', 'datos', 'copy')[i % 4]}", size=14),
            spacer(),
            text(f"{(i * 37) % 100} %", size=13, color="$muted"),
        ]

    def view():
        current = selected()
        return column(padding=16, gap=12)[
            text(f"{n} tareas", size=20, weight=700),
            virtual_list(n, lambda i: item(i, i == current), item_height=36, gap=2, key="lista"),
        ]

    def rebuild(pilot: Pilot) -> None:
        selected.update(lambda s: (s + 1) % 20)  # siempre dentro de la zona visible
        pilot.frame()

    return Bench(
        App(view, size=(960, 640)),
        {
            "rebuild": rebuild,
            "hover": _alternate(lambda p: p.move_to(300, 70), lambda p: p.move_to(300, 110)),
            # Cada paso cambia el rango visible: el frame siguiente reconstruye la lista.
            "scroll": _alternate(lambda p: p.wheel(400), lambda p: p.wheel(-400)),
            "idle": _idle,
        },
        info={"items": n},
    )


# ------------------------------------------------------------ dashboard de 50 paneles


def dashboard_50(scale: float = 1.0) -> Bench:
    n = max(2, int(50 * scale))
    bars = 24
    tick = Signal(0)

    def series(panel: int) -> list[int]:
        t = tick()
        return [12 + (panel * 7 + (i + t) * 13) % 61 for i in range(bars)]

    def panel(p: int):
        values = series(p)
        return card(
            key=f"panel-{p}",
            width=220,
            gap=10,
            bg_hover="$surface_hover",
            on_click=lambda: None,
        )[
            row(align="center")[
                text(f"Métrica {p + 1}", size=13, color="$muted"),
                spacer(),
                badge(f"+{values[-1] % 9}%", tone="success"),
            ],
            text(f"{sum(values):,}".replace(",", "."), size=22, weight=700),
            row(height=64, gap=2, align="end")[
                [box(grow=1, height=v, radius=2, bg="$primary") for v in values]
            ],
        ]

    def view():
        return scroll(key="dashboard", padding=20)[row(wrap=True, gap=16)[[panel(p) for p in range(n)]]]

    def rebuild(pilot: Pilot) -> None:
        tick.update(lambda t: t + 1)
        pilot.frame()

    return Bench(
        App(view, size=(1280, 800)),
        {
            "rebuild": rebuild,
            "hover": _alternate(lambda p: p.move_to(120, 80), lambda p: p.move_to(360, 80)),
            "idle": _idle,
        },
        info={"panels": n, "bars": n * bars},
    )


# ----------------------------------------------------- escribir en un formulario grande


def typing(scale: float = 1.0) -> Bench:
    n = max(5, int(500 * scale))
    query = Signal("")
    labels = [f"Campo {i:03d}" for i in range(n)]

    def view():
        q = query().lower()
        return column(padding=20, gap=12)[
            text_input(query, placeholder="Filtrar…", key="campo"),
            scroll(key="filas", gap=4)[
                [
                    row(key=f"fila-{i}", gap=8, padding=(6, 10), radius=6, bg="$surface")[
                        text(label, size=13),
                        spacer(),
                        text("coincide" if q and q in label.lower() else "—", size=12, color="$muted"),
                    ]
                    for i, label in enumerate(labels)
                ]
            ],
        ]

    def type_char(pilot: Pilot) -> None:
        # Una tecla = un frame: on_change → Signal → reconstrucción completa.
        if len(query()) >= 30:
            query.set("")
        pilot.type("a")

    return Bench(
        App(view, size=(960, 640)),
        {"type": type_char, "idle": _idle},
        setup=lambda p: p.focus("campo"),
        info={"rows": n},
    )


SCENARIOS = [
    Scenario("lista_10k", "Lista de 10 000 filas en un scroll, con selección", list_10k),
    Scenario(
        "lista_10k_memo",
        "La misma lista con cada fila como @component",
        lambda scale: list_10k(scale, memo=True),
    ),
    Scenario(
        "lista_virtual_100k",
        "100 000 filas en una virtual_list con filas @component",
        virtual_100k,
    ),
    Scenario("dashboard_50", "50 paneles con 24 barras cada uno, datos que cambian", dashboard_50),
    Scenario("typing", "Escribir en un campo que filtra un formulario de 500 filas", typing),
]
