"""Dos ventanas, diálogos nativos y menús: la lista de notas en la principal y el detalle aparte.

uv run examples/windows.py                      # abre las dos ventanas
uv run examples/windows.py --png notas.png      # render headless (notas.png y notas-detalle.png)
"""

import sys
from pathlib import Path

from aurora import App, Signal, button, card, column, dialogs, menus, row, spacer, text

notas = Signal(
    [
        ("Ideas", "Probar App.window() en la app de notas"),
        ("Compras", "Café, leche y algo para la cena"),
        ("Trabajo", "Revisar el roadmap hacia la 1.0"),
    ]
)
seleccion = Signal(0)


def abrir_archivo() -> None:
    """El diálogo nativo de abrir: la nota nueva es el archivo elegido."""
    ruta = dialogs.open_file(title="Abrir nota", filters=[("Texto", ["txt", "md"])])
    if ruta is not None:
        texto = Path(ruta).read_text(encoding="utf-8").strip()
        notas.set([*notas(), (Path(ruta).name, texto[:60] or "(vacío)")])
        seleccion.set(len(notas()) - 1)
        detalle_win.open()


def borrar(indice: int) -> None:
    notas.set([nota for i, nota in enumerate(notas()) if i != indice])
    seleccion.set(min(seleccion(), len(notas()) - 1))


def lista():
    return column(padding=20, gap=12)[
        row(align="center")[
            text("Notas", size=20, weight=700),
            spacer(),
            button("Abrir archivo…", abrir_archivo, variant="soft", key="abrir"),
        ],
        [
            card(
                key=f"nota-{i}",
                padding=12,
                gap=4,
                bg="$surface_hover" if seleccion() == i else "$surface",
                shadow=None,
                on_click=lambda i=i: seleccion.set(i),
                on_context_menu=[
                    menus.item("Abrir detalle", lambda i=i: (seleccion.set(i), detalle_win.open())),
                    menus.separator(),
                    menus.item("Eliminar", lambda i=i: borrar(i), enabled=len(notas()) > 1),
                ],
            )[text(titulo, weight=600), text(cuerpo, size=12, color="$muted", max_lines=1)]
            for i, (titulo, cuerpo) in enumerate(notas())
        ],
    ]


def detalle():
    titulo, cuerpo = notas()[seleccion()]
    return column(padding=20, gap=10)[
        text(titulo, size=18, weight=700, key="titulo"),
        text(lambda: f"{seleccion() + 1} de {len(notas())}", size=12, color="$muted"),
        text(cuerpo, color="$muted", key="cuerpo"),
        spacer(),
        button("Cerrar", lambda: detalle_win.close(), variant="ghost", key="cerrar"),
    ]


app = App(
    lista,
    title="Notas",
    size=(420, 380),
    menu=menus.bar(
        menus.submenu(
            "Archivo",
            menus.item("Abrir archivo…", abrir_archivo, shortcut="mod+o"),
            menus.separator(),
            menus.item("Salir", lambda: app.quit(), shortcut="mod+q"),
        )
    ),
)
detalle_win = app.window(detalle, title="Detalle", size=(320, 240))

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--png":
        app.render_png(sys.argv[2])
        detalle_win.render_png(sys.argv[2].replace(".png", "-detalle.png"))
    else:
        app.run()
