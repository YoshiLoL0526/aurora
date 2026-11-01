from aurora import App, Signal, button, column, row, text

count = Signal(0)


def view():
    return column(padding=24, gap=16, bg="$background", align="center")[
        text("Contador de clics del equipo de producto", size=22, weight=700, width=420),
        text(f"Clics: {count()}", key="count", size=18, colr="$muted"),
        row(gap=8)[
            button("Sumar", lambda: count.update(lambda c: c + 1), key="inc"),
            button("Reiniciar", count.set(0), key="reset", variant="sof"),
        ],
    ]


App(view, title="Contador", size=(360, 240)).run()
