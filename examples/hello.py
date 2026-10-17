"""Hola mundo de Aurora: un mini dashboard con estado reactivo.

uv run examples/hello.py                 # abre la ventana
uv run examples/hello.py --png out.png   # render headless
"""

import sys

from aurora import App, Signal, __version__, badge, button, card, column, row, slider, spacer, stat, text

clicks = Signal(0)
step = Signal(1.0)  # el deslizador lo mantiene entre 1 y 50


def snap_step(value: float) -> None:
    """El deslizador da valores continuos: el paso se queda en enteros."""
    step.set(round(value))


def header():
    return row(align="center", gap=12)[
        column(gap=4)[
            text("Panel de control", size=26, weight=700, letter_spacing=-0.4),
            text("Rust + Skia + Taffy, controlado desde Python", size=13, color="$muted"),
        ],
        spacer(),
        badge(f"v{__version__}"),
    ]


def counter():
    return card(gradient=("#1E1A3A", "#0F2A2A", 35), border_color="#2E2A55", gap=18)[
        text("Contador reactivo", size=15, weight=600),
        text(lambda: f"{clicks():,}", size=56, weight=800, letter_spacing=-1.5),
        row(gap=10)[
            button("−", lambda: clicks.update(lambda c: c - round(step())), variant="soft", width=52),
            button("+ Incrementar", lambda: clicks.update(lambda c: c + round(step())), grow=1),
            button("Reset", lambda: clicks.set(0), variant="ghost"),
        ],
        row(align="center", gap=12)[
            text("Paso", size=12, color="$muted"),
            slider(step, min=1, max=50, width=240, key="step", on_change=snap_step),
            text(lambda: f"×{round(step())}", size=12, weight=700, width=32, text_align="end"),
        ],
    ]


def view():
    return column(padding=32, gap=24)[
        header(),
        row(gap=16)[
            stat("USUARIOS ACTIVOS", "12.480", "+8,2%"),
            stat("LATENCIA P95", "38 ms", "−12%"),
            stat("ERRORES", "0,04%", "+0,01", positive=False),
        ],
        counter(),
    ]


app = App(view, title="Aurora · Hola mundo", size=(880, 600))

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--png":
        app.render_png(sys.argv[2])
    else:
        app.run()
