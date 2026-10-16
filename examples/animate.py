"""Animaciones declarativas: una lista de tareas que se reordena, entra y sale con suavidad.

python examples/animate.py               # abre la ventana
python examples/animate.py --png out.png # render headless (estado final, sin animación)
"""

import random
import sys
from dataclasses import dataclass, replace

from aurora import App, Signal, animate, badge, box, button, card, column, row, spacer, text


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
        text(t.title, color="$muted" if t.done else "$text"),
        spacer(),
        button("Quitar", lambda: remove(t.id), variant="ghost"),
    ]


def details():
    if not modal():
        return None
    return box(
        key="modal",
        layer="overlay",
        position="absolute",
        top=0,
        right=0,
        bottom=0,
        left=0,
        bg="#00000088",
        align="center",
        justify="center",
        enter=animate.fade(),
        exit=animate.fade(),
        on_click=lambda: modal.set(False),
    )[
        card(width=360, capture=True, enter=animate.zoom(0.94), gap=12)[
            text("Animaciones declarativas", size=18, weight=700),
            text(
                "Cada fila declara cómo cambia, entra y sale. El núcleo Rust interpola los "
                "frames sin volver a llamar a Python.",
                color="$muted",
            ),
            row(justify="end")[button("Cerrar", lambda: modal.set(False), variant="soft")],
        ]
    ]


def view():
    done = sum(t.done for t in tasks())
    return box()[
        column(padding=32, gap=20, max_width=640)[
            row(align="center", gap=12)[
                text("Tareas", size=26, weight=700),
                badge(f"{done}/{len(tasks())}", tone="success" if done else "accent"),
                spacer(),
                button("Barajar", shuffle, variant="soft"),
                button("¿Cómo funciona?", lambda: modal.set(True), variant="soft"),
                button("+ Añadir", add),
            ],
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
