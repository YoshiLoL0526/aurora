from dataclasses import dataclass

from aurora import App, Signal, button, checkbox, column, row, text, text_input


@dataclass(frozen=True)
class Task:
    n: int
    title: str
    done: bool = False


tasks: Signal[list[Task]] = Signal([])
new = Signal("")
show = Signal("all")


def add(_: object = None) -> None:
    title = new().strip()
    if title:
        tasks.update(lambda ts: [*ts, Task(len(ts) + 1, title)])
        new.set("")


def toggle(n: int, done: bool) -> None:
    tasks.update(lambda ts: [Task(t.n, t.title, done) if t.n == n else t for t in ts])


def visible(t: Task) -> bool:
    return show() == "all" or (show() == "done") == t.done


def view():
    pending = sum(not t.done for t in tasks())
    return column(padding=24, gap=16)[
        text("Tareas", size=24, weight=700),
        row(gap=8)[
            text_input(new, placeholder="Nueva tarea", on_submit=add, key="new", grow=1),
            button("Añadir", add, key="add"),
        ],
        row(gap=8)[
            button("Todas", lambda: show.set("all"), key="filter-all", variant="soft"),
            button("Pendientes", lambda: show.set("pending"), key="filter-pending", variant="soft"),
            button("Hechas", lambda: show.set("done"), key="filter-done", variant="soft"),
        ],
        column(gap=8)[
            [
                row(key=f"task-{t.n}", gap=8)[
                    checkbox(t.done, t.title, on_change=lambda v, n=t.n: toggle(n, v), key=f"toggle-{t.n}")
                ]
                for t in tasks()
                if visible(t)
            ]
        ],
        text(f"{pending} pendientes", key="remaining", color="$muted"),
    ]


App(view, title="Tareas", size=(520, 600)).run()
