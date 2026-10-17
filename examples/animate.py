"""Animaciones declarativas: una lista de tareas que se reordena, entra y sale con suavidad.

El modal es el componente `dialog` (con su entrada y salida ya incluidas) y la barra de
progreso crece hasta su nuevo valor al marcar tareas.

uv run examples/animate.py               # abre la ventana
uv run examples/animate.py --png out.png # render headless (estado final, sin animación)
"""

import random
import sys
from dataclasses import dataclass, replace

from aurora import App, Signal, animate, badge, box, button, column, dialog, progress, row, spacer, text


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    done: bool = False


TITLES = [
    "Revisar el informe trimestral",
    "Preparar la demo del jueves",
    "Responder a soporte",
    "Actualizar dependencias",
    "Escribir la nota de versión",
    "Planificar el sprint",
    "Revisar el PR de Lucía",
]

tasks = Signal([Task(i, t) for i, t in enumerate(TITLES[:4])])
next_id = Signal(len(TITLES[:4]))
modal = Signal(False)


def add():
    i = next_id()
    next_id.set(i + 1)
    tasks.update(lambda ts: [Task(i, TITLES[i % len(TITLES)]), *ts])


def remove(task_id):
    tasks.update(lambda ts: [t for t in ts if t.id != task_id])


def toggle(task_id):
    tasks.update(lambda ts: [replace(t, done=not t.done) if t.id == task_id else t for t in ts])


def shuffle():
    tasks.update(lambda ts: random.sample(ts, len(ts)))


def task_row(t):
    return row(
        key=f"tarea-{t.id}",
        align="center",
        gap=12,
        padding=(12, 14),
        radius="$md",
        bg="#1F3A33" if t.done else "$surface",
        border_width=1,
        border_color="#2F6B5A" if t.done else "$border",
        # Los cambios de color se funden, la fila se desliza cuando el layout la mueve,
        # entra deslizándose desde arriba y sale encogiéndose.
        transition=animate.spring(),
        animate_layout=True,
        enter=animate.slide(y=-12),
        exit=animate.zoom(0.9),
    )[
        box(
            key=f"check-{t.id}",
            width=18,
            height=18,
            radius=6,
            bg="$success" if t.done else None,
            border_width=2,
            border_color="$success" if t.done else "$muted",
            transition=animate.tween(0.15),
            on_click=lambda: toggle(t.id),
        ),
        text(
            t.title,
            color="$muted" if t.done else "$text",
            # El color del texto también funde al cambiar de estado (el texto necesita
            # su propia transición: la del contenedor no se hereda).
            transition=animate.tween(0.15),
            max_lines=1,
            shrink=1,
        ),
        spacer(),
        button("Quitar", lambda: remove(t.id), variant="ghost"),
    ]


def details():
    """El diálogo trae su propia animación: la tarjeta entra con un zoom suave y sale fundiéndose."""
    return dialog(
        modal,
        column(gap=16)[
            text(
                "Cada fila declara cómo cambia y cómo entra y sale: transition funde sus colores, "
                "animate_layout la desliza cuando la lista se reordena, y enter y exit la "
                "presentan y la retiran. El núcleo Rust interpola los frames sin volver a "
                "llamar a Python.",
                color="$muted",
                line_height=1.4,
            ),
            row(justify="end")[button("Cerrar", lambda: modal.set(False), variant="soft")],
        ],
        title="Animaciones declarativas",
        key="details",
        width=420,
    )


def view():
    done = sum(t.done for t in tasks())
    total = len(tasks())
    return box()[
        column(padding=32, gap=20, max_width=640)[
            row(align="center", gap=12)[
                text("Tareas", size=26, weight=700),
                badge(f"{done}/{total}", tone="success" if done else "accent"),
                spacer(),
                button("Barajar", shuffle, variant="soft"),
                button("¿Cómo funciona?", lambda: modal.set(True), variant="soft", key="help"),
                button("+ Añadir", add),
            ],
            # Al marcar una tarea, la barra crece (animada) hasta su nuevo valor.
            progress(done, max=max(total, 1), height=6),
            column(gap=8)[[task_row(t) for t in tasks()]],
        ],
        details(),
    ]


app = App(view, title="Aurora · Animaciones", size=(720, 560))

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--png":
        app.render_png(sys.argv[2])
    else:
        app.run()
