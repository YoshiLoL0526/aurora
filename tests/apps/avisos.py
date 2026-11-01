"""App con problemas de layout a propósito, para los avisos de `aurora tree` y `check`."""

from aurora import App, box, column, row, text

LARGO = "Supercalifragilisticoespialidoso"

app = App(
    lambda: column(padding=16, gap=8)[
        row(width=60, key="estrecha")[text(LARGO, key="desborda")],
        row(width=60, overflow="hidden")[text(LARGO, key="cortado")],
        text("Una frase larga en una caja muy baja", key="bajo", width=80, height=20),
        box(on_click=lambda: None, key="icono", width=24, height=24, bg="$primary"),
        # Un control con label pero fuera de la ventana de 400 px.
        box(
            on_click=lambda: None,
            key="lejos",
            label="Lejos",
            width=40,
            height=40,
            position="absolute",
            left=900,
        ),
        text("Bien", key="bien"),
    ],
    size=(400, 300),
)
app.run()
