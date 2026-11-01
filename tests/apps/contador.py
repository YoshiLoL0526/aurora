"""App pequeña para los tests de `aurora shot/tree/check/pilot`: un contador y un campo."""

import sys

from aurora import App, Signal, button, column, row, text, text_input

count = Signal(0)
name = Signal("")


def view():
    return column(padding=24, gap=12)[
        text(lambda: f"Clics: {count()}", key="total", size=20),
        row(gap=8)[
            button("Sumar", lambda: count.update(lambda c: c + 1), key="add"),
            button("Reset", lambda: count.set(0), key="reset", variant="ghost"),
        ],
        text_input(name, placeholder="Tu nombre", key="name"),
        text(lambda: f"Hola, {name()}" if name() else "Sin nombre", key="greeting"),
    ]


app = App(view, title="Contador", size=(400, 300))

if __name__ == "__main__":
    # Lo que pasa en `python contador.py --png x.png`: los comandos no le pasan argumentos.
    if len(sys.argv) > 1:
        raise SystemExit("argumentos inesperados")
    app.run()
