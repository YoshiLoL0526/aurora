"""Tabla de datos con `table`: 100 000 filas ordenables, columnas redimensionables y filtro.

uv run examples/table.py               # abre la ventana
uv run examples/table.py --png out.png # render headless
"""

import random
import sys
from dataclasses import dataclass

from aurora import App, Column, Signal, badge, column, row, spacer, table, text, text_input

random.seed(11)

CIUDADES = ["Madrid", "Lima", "Bogotá", "Santiago", "México", "Buenos Aires", "Montevideo"]
NOMBRES = ["Ana", "Bruno", "Carla", "Diego", "Elena", "Fabián", "Gala", "Hugo", "Inés", "Jaime"]
APELLIDOS = ["García", "López", "Martín", "Pérez", "Sánchez", "Torres", "Vega", "Ruiz"]
ESTADOS = {"activo": "success", "pausado": "accent", "baja": "danger"}


@dataclass(frozen=True)
class Cliente:
    id: int
    nombre: str
    ciudad: str | None
    pedidos: int
    total: float
    estado: str


CLIENTES = [
    Cliente(
        id=i + 1,
        nombre=f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}",
        ciudad=random.choice(CIUDADES) if random.random() > 0.05 else None,
        pedidos=random.randint(0, 240),
        total=round(random.lognormvariate(6, 1.1), 2),
        estado=random.choices(list(ESTADOS), weights=(8, 2, 1))[0],
    )
    for i in range(100_000)
]


def _euros(v: float) -> str:
    """`1234.5` → `"1.234,50 €"`."""
    return f"{v:,.2f} €".translate(str.maketrans(",.", ".,"))


COLUMNAS = [
    Column("id", "Nº", width=90, align="end"),
    Column("nombre", "Cliente", width=200),
    Column("ciudad", "Ciudad", width=150),
    Column("pedidos", "Pedidos", width=110, align="end"),
    Column("total", "Total", width=140, align="end", format=_euros),
    Column("estado", "Estado", width=120, cell=lambda c: badge(c.estado, tone=ESTADOS[c.estado])),
]

busqueda = Signal("")
elegido: Signal[Cliente | None] = Signal(None)
# Resultados del último filtro: la misma lista mientras no cambie la búsqueda, así
# la tabla reutiliza el orden calculado al desplazarse.
_filtro: dict[str, list[Cliente]] = {}


def filtrados() -> list[Cliente]:
    q = busqueda().strip().casefold()
    if q not in _filtro:
        _filtro.clear()
        _filtro[q] = [c for c in CLIENTES if q in c.nombre.casefold()] if q else CLIENTES
    return _filtro[q]


def view():
    filas = filtrados()
    actual = elegido()
    return column(padding=28, gap=16)[
        row(align="center", gap=12)[
            text("Clientes", size=26, weight=700),
            text(f"{len(filas):,} filas".replace(",", "."), color="$muted"),
            spacer(),
            text_input(busqueda, placeholder="Buscar por nombre…", width=260, key="buscar"),
        ],
        table(filas, COLUMNAS, key="clientes", on_row_click=elegido.set),
        text(
            f"Seleccionado: {actual.nombre} · {actual.ciudad or '—'}" if actual else "Pulsa una fila",
            color="$muted",
        ),
    ]


app = App(view, title="Aurora · Tabla", size=(980, 700))

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--png":
        app.render_png(sys.argv[2])
    else:
        app.run()
