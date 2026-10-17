"""Gráficos nativos con `chart`: línea, área, barras y dispersión.

uv run examples/charts.py               # abre la ventana
uv run examples/charts.py --png out.png # render headless
"""

import random
import sys
from typing import Literal

import numpy as np
import polars as pl

from aurora import (
    App,
    Element,
    Signal,
    button,
    card,
    chart,
    column,
    component,
    row,
    scroll,
    segmented,
    spacer,
    text,
)

random.seed(7)
rng = np.random.default_rng(7)

# --- datos -------------------------------------------------------------------

N = 240
x = np.arange(N, dtype=np.float64)
latencia = pl.DataFrame(
    {
        "p50": 40 + 18 * np.sin(x / 22) + rng.normal(0, 3, N),
        "p95": 90 + 40 * np.sin(x / 22 + 0.7) + rng.normal(0, 6, N),
    }
)

DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
cierres = np.array([12.0, 18.0, 9.0, 24.0, 30.0, 7.0, 4.0])

puntos_x = rng.normal(0, 1, 500)
puntos_y = puntos_x * 1.8 + rng.normal(0, 0.9, 500)

# Una señal de un millón de muestras: al dibujarla se reduce con LTTB (~2 puntos
# por píxel), así que se mueve suave con la rueda y el arrastre.
t = np.arange(1_000_000, dtype=np.float64)
senal = np.sin(t / 9_000) + np.sin(t / 41) * 0.22

# Las series "en vivo" se mutan en sitio: el gráfico relee la misma memoria.
ventana = np.full(120, 0.5)
version = Signal(0)

# Forma del gráfico de cierres, elegida con el `segmented` de su tarjeta.
Forma = Literal["bar", "area", "line"]
forma: Signal[Forma] = Signal("bar")


def nuevo_dato() -> None:
    ventana[:-1] = ventana[1:]
    ventana[-1] = random.random()
    cierres[:] = np.clip(cierres + rng.integers(-2, 4, 7), 0, 40)
    version.set(version() + 1)


# --- tarjetas ----------------------------------------------------------------
# Como componentes memorizados, cada gráfico se vuelve a grabar solo cuando
# cambian sus datos (o su tamaño).


@component
def latencias() -> Element:
    """Dos series de un DataFrame de polars (`to_numpy` comparte la memoria)."""
    return card(grow=3, width=0)[
        text("Latencia por petición", weight=600),
        chart(latencia, names=["p50", "p95"], height=190),
    ]


@component
def en_vivo(_version: int) -> Element:
    return card(grow=2, width=0)[
        text("Carga en vivo (numpy, mutado en sitio)", weight=600),
        chart(ventana, kind="area", color="$accent", names=["cpu"], height=190, y_min=0, y_max=1),
    ]


@component
def cierres_semana(kind: Forma, _version: int) -> Element:
    return card(grow=1, width=0, gap=12)[
        row(align="center")[
            text("Tareas cerradas", weight=600),
            spacer(),
            segmented(
                [("bar", "Barras"), ("area", "Área"), ("line", "Línea")],
                forma,
                key="cierres-forma",
                width=200,
            ),
        ],
        chart(cierres, kind=kind, labels=DIAS, height=150, color="$primary", bar_width=0.62),
    ]


@component
def dispersion() -> Element:
    return card(grow=1, width=0)[
        text("Dispersión", weight=600),
        chart(puntos_y, x=puntos_x, kind="scatter", height=160, color="$accent", point_size=3),
    ]


@component
def senal_larga() -> Element:
    """Un millón de puntos con zoom (rueda) y pan (arrastre)."""
    return card(grow=1, width=0)[
        text("Señal de 1 000 000 de puntos · rueda para acercar, arrastra para mover", weight=600),
        chart(senal, zoom=True, key="senal", height=180, color="$success"),
    ]


def view():
    return scroll(key="pagina")[
        column(padding=28, gap=18)[
            row(align="center")[
                text("Charts", size=26, weight=700),
                spacer(),
                button("Nuevo dato", nuevo_dato, key="nuevo-dato"),
            ],
            row(gap=16, align="stretch")[latencias(), en_vivo(version())],
            row(gap=16, align="stretch")[cierres_semana(forma(), version()), dispersion()],
            row(align="stretch")[senal_larga()],
        ]
    ]


app = App(view, title="Aurora · Charts", size=(980, 860))

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--png":
        app.render_png(sys.argv[2])
    else:
        app.run()
