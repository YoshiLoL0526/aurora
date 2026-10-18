"""Vive en la bandeja: cierra la ventana, la app sigue y avisa con notificaciones.

uv run examples/tray.py                    # abre la ventana y su bandeja
uv run examples/tray.py --png bandeja.png  # render headless
"""

import sys
from pathlib import Path

from aurora import App, Signal, badge, button, card, column, menus, row, scroll, spacer, text

ICONO = Path(__file__).with_name("icon.png")

recordatorios = Signal(
    [
        "Probar `app.main.close()` y reabrir desde la bandeja",
        "El menú de la bandeja comparte los `Signal` con la ventana",
        "«Salir» es lo único que termina la app",
    ]
)


def añadir() -> None:
    recordatorios.set([*recordatorios(), f"Recordatorio {len(recordatorios()) + 1}"])
    # La notificación la pinta el sistema aunque la ventana esté cerrada; en
    # una app empaquetada lleva la identidad de la app (la registra sola).
    # El clic en el aviso reabre la ventana.
    app.notify(
        "Recordatorio añadido",
        f"Ya hay {len(recordatorios())} en la lista",
        icon=ICONO,
        on_click=app.main.open,
    )


def alternar() -> None:
    """Muestra u oculta la ventana principal (el cierre no termina la app)."""
    if app.main.is_open:
        app.main.close()
    else:
        app.main.open()


def borrar_todo() -> None:
    recordatorios.set([])


def view():
    return column(padding=24, gap=16)[
        row(align="center", gap=10)[
            text("Recordatorios", size=24, weight=700),
            badge(lambda: str(len(recordatorios()))),
            spacer(),
            button("+1", añadir, key="añadir"),
            button("Ocultar ventana", alternar, variant="soft", key="ocultar"),
        ],
        text(
            "La app sigue viva en la bandeja del sistema: ábrela con su icono, su doble clic o "
            "pulsando la notificación, y ciérrala con la X cuando quieras — solo «Salir» la "
            "termina.",
            size=13,
            color="$muted",
        ),
        scroll(grow=1, key="scroll")[
            column(gap=8)[
                [
                    card(padding=12, key=f"nota-{i}")[text(nota, size=14)]
                    for i, nota in enumerate(recordatorios())
                ]
            ]
        ],
    ]


app = App(view, title="Aurora en la bandeja", size=(560, 420), motion=False)
app.tray(
    ICONO,
    tooltip="Aurora: recordatorios",
    menu=[
        menus.item("Mostrar u ocultar la ventana", alternar),
        menus.item("Añadir recordatorio", añadir),
        menus.separator(),
        menus.submenu("Peligro", menus.item("Borrar todo", borrar_todo)),
        menus.item("Salir", lambda: app.quit()),
    ],
    # Con menú, un clic normal lo abre; el doble clic sí llega a la app.
    on_double_click=lambda boton: app.main.open(),
)

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--png":
        app.render_png(sys.argv[2])
    else:
        app.run()
