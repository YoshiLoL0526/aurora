"""Hola mundo de Aurora: un mini dashboard con estado reactivo.

python examples/hello.py            # abre la ventana
python examples/hello.py --png out.png   # render headless
"""

import sys

from aurora import App, Signal, badge, button, card, column, row, spacer, stat, text

clicks = Signal(0)
step = Signal(1)


def header():
    return row(align="center", gap=12)[
        column(gap=4)[
            text("Panel de control", size=26, weight=700, letter_spacing=-0.4),
            text("Rust + Skia + Taffy, controlado desde Python", size=13, color="$muted"),
        ],
        spacer(),
        badge("v0.2"),
    ]


def counter():
    return card(gradient=("#1E1A3A", "#0F2A2A", 35), border_color="#2E2A55", gap=18)[
        row(align="center")[
            text("Contador reactivo", size=15, weight=600),
            spacer(),
            text(lambda: f"paso ×{step()}", size=12, color="$muted"),
        ],
        text(lambda: f"{clicks():,}", size=56, weight=800, letter_spacing=-1.5),
        row(gap=10)[
            button("−", lambda: clicks.update(lambda c: c - step()), variant="soft", width=52),
            button("+ Incrementar", lambda: clicks.update(lambda c: c + step()), grow=1),
            button("×10", lambda: step.update(lambda s: 1 if s == 10 else 10), variant="soft"),
            button("Reset", lambda: clicks.set(0), variant="ghost"),
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
