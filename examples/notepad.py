"""Bloc de notas: diálogos nativos, menú con atajos, soltar archivos y «cambios sin guardar».

uv run examples/notepad.py                    # abre la ventana
uv run examples/notepad.py --png nota.png     # render headless
"""

import sys
from pathlib import Path

from aurora import (
    App,
    KeyEvent,
    Signal,
    button,
    column,
    dialog,
    dialogs,
    menus,
    row,
    scroll,
    spacer,
    text,
    textarea,
)

contenido = Signal("")
ruta = Signal[Path | None](None)  # el archivo abierto, si lo hay
sucio = Signal(False)
confirmar = Signal(False)
arrastrando = Signal(False)  # hay archivos del sistema pasando sobre la ventana


def nombre() -> str:
    archivo = ruta()
    return archivo.name if archivo is not None else "Sin título"


def titulo(_=None) -> None:
    """El título de la ventana refleja el archivo y si hay cambios sin guardar."""
    app.main.title = f"{nombre()}{' •' if sucio() else ''} — Bloc de notas"


# Cada tecla en el editor marca el documento como sucio; el título lo enseña.
contenido.subscribe(lambda _: sucio.set(True))
ruta.subscribe(titulo)
sucio.subscribe(titulo)


def nuevo() -> None:
    contenido.set("")
    ruta.set(None)
    sucio.set(False)


def abrir() -> None:
    elegida = dialogs.open_file(title="Abrir nota", filters=[("Texto", ["txt", "md"])])
    if elegida is not None:
        cargar(Path(elegida))


def soltar(archivos: list[str]) -> None:
    """Arrastrar un archivo desde el explorador sobre la ventana lo abre."""
    cargar(Path(archivos[0]))


def cargar(archivo: Path) -> None:
    try:
        contenido.set(archivo.read_text(encoding="utf-8"))
    except OSError as error:
        print(f"aurora: no se pudo leer {archivo}: {error}", file=sys.stderr)
        return
    ruta.set(archivo)
    sucio.set(False)


def escribir(archivo: Path) -> bool:
    try:
        archivo.write_text(contenido(), encoding="utf-8")
    except OSError as error:
        print(f"aurora: no se pudo escribir {archivo}: {error}", file=sys.stderr)
        return False
    ruta.set(archivo)
    sucio.set(False)
    return True


def guardar() -> bool:
    archivo = ruta()
    if archivo is None:
        return guardar_como()
    return escribir(archivo)


def guardar_como() -> bool:
    elegida = dialogs.save_file(
        title="Guardar nota",
        default_name=nombre(),
        filters=[("Texto", ["txt", "md"])],
    )
    return elegida is not None and escribir(Path(elegida))


def salir() -> None:
    if sucio():
        confirmar.set(True)  # el diálogo decide si se descarta
    else:
        app.quit()


def descartar() -> None:
    confirmar.set(False)
    app.quit()


def al_cerrar() -> bool:
    """La X de la ventana pasa por la misma confirmación."""
    if not sucio():
        return True
    confirmar.set(True)
    return False


def atajos(e: KeyEvent) -> bool | None:
    """En Linux no hay barra de menús: los atajos los atiende la app."""
    if e.matches("mod+o"):
        abrir()
        return True
    if e.matches("mod+s"):
        guardar()
        return True
    if e.matches("mod+n"):
        nuevo()
        return True
    return None


def view():
    return column(
        padding=16,
        gap=12,
        on_key=atajos,
        on_drop=soltar,
        on_drop_hover=lambda archivos: arrastrando.set(archivos is not None),
    )[
        row(align="center", gap=10)[
            text(lambda: nombre(), weight=700, key="nombre"),
            text(lambda: "• sin guardar" if sucio() else "", size=12, color="$muted"),
            spacer(),
            button("Abrir…", abrir, variant="soft", key="abrir"),
            button("Guardar", guardar, key="guardar"),
        ],
        scroll(grow=1, key="scroll")[
            textarea(
                contenido,
                placeholder="Escribe algo… o suelta aquí un archivo",
                rows=16,
                border_color="$primary" if arrastrando() else "$border",
                grow=1,
                key="editor",
            )
        ],
        dialog(
            confirmar,
            column(gap=14)[
                text("Tienes cambios sin guardar", weight=700),
                text("Si sales ahora, se perderán.", size=13, color="$muted"),
                row(gap=8, justify="end")[
                    button("Cancelar", lambda: confirmar.set(False), variant="ghost"),
                    button("Salir sin guardar", descartar, variant="soft", color="$danger"),
                ],
            ],
            title="¿Salir?",
            key="salida",
        ),
    ]


app = App(
    view,
    title="Bloc de notas",
    size=(720, 520),
    menu=menus.bar(
        menus.submenu(
            "Archivo",
            menus.item("Nuevo", nuevo, shortcut="mod+n"),
            menus.item("Abrir…", abrir, shortcut="mod+o"),
            menus.item("Guardar", guardar, shortcut="mod+s"),
            menus.separator(),
            menus.item("Salir", salir, shortcut="mod+q"),
        ),
        menus.submenu(
            "Edición",
            menus.predefined("undo"),
            menus.predefined("redo"),
            menus.separator(),
            menus.predefined("cut"),
            menus.predefined("copy"),
            menus.predefined("paste"),
            menus.predefined("select_all"),
        ),
    ),
)
app.main.on_close = al_cerrar
titulo()  # el título compuesto desde el principio

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--png":
        app.render_png(sys.argv[2])
    else:
        app.run()
