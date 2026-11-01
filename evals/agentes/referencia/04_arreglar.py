from aurora import App, Signal, button, column, row, text

count = Signal(0)


def view():
    return column(padding=24, gap=16, bg="$background", align="center")[
        text("Contador de clics del equipo de producto", size=22, weight=700, text_align="center"),
        text(lambda: f"Clics: {count()}", key="count", size=18, color="$muted"),
        row(gap=8)[
            button("Sumar", lambda: count.update(lambda c: c + 1), key="inc"),
            button("Reiniciar", lambda: count.set(0), key="reset", variant="soft"),
        ],
    ]


App(view, title="Contador", size=(360, 240)).run()
