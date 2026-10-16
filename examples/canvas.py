"""Dibujo inmediato con `canvas`: un gráfico de líneas y un indicador circular.

uv run examples/canvas.py               # abre la ventana
uv run examples/canvas.py --png out.png # render headless
"""

import math
import random
import sys

from aurora import App, Canvas, Signal, button, canvas, card, column, component, row, spacer, text

random.seed(7)
series = Signal([50 + 30 * math.sin(i / 4) + random.uniform(-8, 8) for i in range(40)])
load = Signal(0.62)


def add_point() -> None:
    values = series()
    series.set([*values[1:], max(0.0, min(100.0, values[-1] + random.uniform(-15, 15)))])
    load.set(random.uniform(0.1, 0.95))


def line_chart(c: Canvas) -> None:
    values = series()
    left, bottom = 36, c.height - 24
    w, h = c.width - left - 8, bottom - 8
    # Rejilla y etiquetas del eje y.
    for v in (0, 25, 50, 75, 100):
        y = bottom - v / 100 * h
        c.line(left, y, left + w, y, stroke="$border", dash=(3, 4))
        c.text(left - 8, y, v, align="right", baseline="middle", color="$muted", size=11)
    step = w / (len(values) - 1)
    points = [(left + i * step, bottom - v / 100 * h) for i, v in enumerate(values)]
    # Área bajo la curva y la propia línea.
    c.polygon([(left, bottom), *points, (left + w, bottom)], fill="$glow")
    c.polyline(points, stroke="$primary", stroke_width=2.5, cap="round")
    x, y = points[-1]
    c.circle(x, y, 5, fill="$primary", stroke="$surface", stroke_width=2)


def gauge(c: Canvas) -> None:
    cx, cy = c.width / 2, c.height / 2 + 10
    r = min(c.width, c.height) / 2 - 16
    c.arc(cx, cy, r, 135, 270, stroke="$border", stroke_width=12, cap="round")
    value = load()
    color = "$danger" if value > 0.8 else "$accent"
    c.arc(cx, cy, r, 135, 270 * value, stroke=color, stroke_width=12, cap="round")
    c.text(cx, cy, f"{value:.0%}", align="center", baseline="middle", size=30, weight=700)
    c.text(cx, cy + 26, "uso medio", align="center", baseline="middle", size=12, color="$muted")


# Como componentes memorizados, cada canvas solo vuelve a dibujarse cuando cambia
# el `Signal` que lee su función de dibujo (o su tamaño).
@component
def chart_card():
    return card(grow=1)[
        text("Peticiones por segundo", weight=600),
        canvas(line_chart, height=220),
    ]


@component
def gauge_card():
    return card(width=240)[
        text("Carga del clúster", weight=600),
        canvas(gauge, height=220),
    ]


def view():
    return column(padding=32, gap=20)[
        row(align="center")[
            text("Canvas", size=26, weight=700),
            spacer(),
            button("Nuevo dato", add_point),
        ],
        row(gap=16)[chart_card(), gauge_card()],
    ]


app = App(view, title="Aurora · Canvas", size=(880, 400))

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--png":
        app.render_png(sys.argv[2])
    else:
        app.run()
