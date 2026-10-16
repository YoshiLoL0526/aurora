"""Aurora Studio — demo completa de capacidades.

Una app de gestión de proyectos con:
  • navegación entre 4 vistas (Resumen, Tablero, Equipo, Ajustes) con estado global en Signals
  • valores derivados (KPIs, progreso por proyecto, carga del equipo) calculados en cada build
  • gráfico de barras interactivo construido solo con primitivas (clic en una barra = detalle)
  • tablero kanban: búsqueda, filtros por etiqueta, mover tareas y eliminar con confirmación
  • formulario de nueva tarea en un modal: text_input con autofocus, select y Enter para crear
  • ajustes con tabs, switch, checkbox, select y textarea enlazados a Signals
  • scroll por página, tooltips, teclado (Tab, Esc, Ctrl/Cmd+N) y tema claro/oscuro reactivo
  • hover/pressed animados en Rust en todos los elementos clicables

    uv run examples/studio.py               # ventana
    uv run examples/studio.py --png out/    # renderiza varias pantallas a PNG
"""

from __future__ import annotations

import io
import itertools
import sys
from dataclasses import dataclass, replace
from pathlib import Path

from aurora import (
    DAYLIGHT,
    MIDNIGHT,
    App,
    Element,
    KeyEvent,
    Signal,
    badge,
    box,
    button,
    card,
    checkbox,
    column,
    divider,
    row,
    scroll,
    select,
    spacer,
    stat,
    switch,
    tabs,
    text,
    text_input,
    textarea,
)

# ════════════════════════════════════════════════════════════════════ modelo


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    project: str
    tag: str
    priority: str  # alta | media | baja
    status: str  # todo | doing | done
    assignee: str
    points: int


@dataclass(frozen=True)
class Member:
    name: str
    role: str
    color: str
    capacity: int

    @property
    def initials(self) -> str:
        return "".join(p[0] for p in self.name.split()[:2]).upper()


PROJECTS = {"Aurora UI": "#7C5CFF", "Agentes IA": "#22D3B6", "Índice on-chain": "#F59E0B"}
PRIORITY_COLORS = {"alta": "#F87171", "media": "#F59E0B", "baja": "#8A91A8"}
STATUSES = [("todo", "Pendiente", "#8A91A8"), ("doing", "En curso", "#7C5CFF"), ("done", "Hecho", "#34D399")]
TAGS = ["backend", "frontend", "infra", "diseño"]

TEAM = [
    Member("Raidel Pérez", "Fullstack · Lead", "#7C5CFF", 21),
    Member("Ana Souza", "Diseño de producto", "#EC4899", 13),
    Member("Lucas Martins", "Backend · Rust", "#22D3B6", 18),
    Member("Carla Méndez", "Infra & DevOps", "#F59E0B", 13),
]

_ids = itertools.count(1)


def _t(title, project, tag, priority, status, assignee, points) -> Task:
    return Task(next(_ids), title, project, tag, priority, status, assignee, points)


SEED = (
    _t("Signals de grano fino con diff por key", "Aurora UI", "backend", "alta", "doing", "Raidel Pérez", 8),
    _t("Backend GPU de Skia (Metal/D3D/Vulkan)", "Aurora UI", "infra", "alta", "todo", "Lucas Martins", 13),
    _t(
        "Componente de input de texto con IME y selección",
        "Aurora UI",
        "frontend",
        "media",
        "todo",
        "Raidel Pérez",
        8,
    ),
    _t("Sistema de tokens y tema claro", "Aurora UI", "diseño", "media", "done", "Ana Souza", 3),
    _t("Router de intents WhatsApp → JIRA", "Agentes IA", "backend", "alta", "doing", "Lucas Martins", 5),
    _t("Prompts de clasificación de tickets", "Agentes IA", "backend", "media", "done", "Raidel Pérez", 3),
    _t("Dashboard de métricas del agente", "Agentes IA", "frontend", "baja", "todo", "Ana Souza", 5),
    _t("Pipeline de despliegue por cliente", "Agentes IA", "infra", "media", "doing", "Carla Méndez", 5),
    _t("Rebalanceo semanal del vault", "Índice on-chain", "backend", "alta", "todo", "Lucas Martins", 8),
    _t("Auditoría de contratos", "Índice on-chain", "infra", "alta", "done", "Carla Méndez", 8),
    _t("Landing con composición del índice", "Índice on-chain", "diseño", "baja", "done", "Ana Souza", 3),
)

WEEKS = {
    "Esta semana": [5, 8, 6, 11, 9, 4, 2],
    "Semana pasada": [3, 6, 9, 7, 5, 6, 1],
}
DAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

# ═════════════════════════════════════════════════════════════════════ estado

tasks: Signal[tuple[Task, ...]] = Signal(SEED)
page = Signal("resumen")
active_tags: Signal[frozenset[str]] = Signal(frozenset())
theme = Signal(MIDNIGHT)
modal: Signal[tuple | None] = Signal(None)  # ("delete", id) | ("about",)
toast: Signal[str | None] = Signal(None)
following: Signal[frozenset[str]] = Signal(frozenset({"Ana Souza"}))
week = Signal("Esta semana")
selected_day: Signal[int | None] = Signal(3)
query = Signal("")

# Formulario de nueva tarea
new_title = Signal("")
new_project = Signal("Aurora UI")
new_priority = Signal("media")
new_tag = Signal("frontend")
new_assignee = Signal(TEAM[0].name)

# Ajustes
settings_tab = Signal("general")
language = Signal("es")
signature = Signal("")
weekly_digest = Signal(True)
notify_assigned = Signal(True)
notify_mentions = Signal(False)

# ══════════════════════════════════════════════════════════════════ acciones


def notify(msg: str) -> None:
    toast.set(msg)


def move(task_id: int, delta: int) -> None:
    order = [s for s, _, _ in STATUSES]

    def step(t: Task) -> Task:
        if t.id != task_id:
            return t
        idx = max(0, min(len(order) - 1, order.index(t.status) + delta))
        return replace(t, status=order[idx])

    tasks.update(lambda ts: tuple(step(t) for t in ts))
    moved = next(t for t in tasks() if t.id == task_id)
    label = next(lbl for s, lbl, _ in STATUSES if s == moved.status)
    notify(f"«{moved.title[:28]}…» → {label}")


def confirm_delete() -> None:
    if (current := modal()) is None:
        return
    _, task_id = current
    victim = next(t for t in tasks() if t.id == task_id)
    tasks.update(lambda ts: tuple(t for t in ts if t.id != task_id))
    modal.set(None)
    notify(f"Tarea eliminada: {victim.title[:32]}")


def open_new_task() -> None:
    modal.set(("new",))


def create_task(_text: str | None = None) -> None:
    title = new_title().strip()
    if not title:
        return
    project = new_project()
    tasks.update(lambda ts: (*ts, _t(title, project, new_tag(), new_priority(), "todo", new_assignee(), 3)))
    new_title.set("")
    modal.set(None)
    notify(f"Nueva tarea en {project}")


def toggle_tag(tag: str) -> None:
    active_tags.update(lambda tags: tags ^ {tag})


def toggle_follow(name: str) -> None:
    following.update(lambda f: f ^ {name})
    notify(("Siguiendo a " if name in following() else "Dejaste de seguir a ") + name.split()[0])


def toggle_theme() -> None:
    theme.set(DAYLIGHT if theme() is MIDNIGHT else MIDNIGHT)


# ═══════════════════════════════════════════════════════════ piezas pequeñas


def avatar(member_or_name: Member | str, size: int = 32, **style) -> Element:
    m = (
        member_or_name
        if isinstance(member_or_name, Member)
        else next(x for x in TEAM if x.name == member_or_name)
    )
    return box(
        width=size,
        height=size,
        radius="$full",
        align="center",
        justify="center",
        gradient=(m.color, m.color + "99", 45),
        **style,
    )[text(m.initials, size=size * 0.36, weight=700, color="#FFFFFF")]


def pill(label: str, color: str, *, solid: bool = False) -> Element:
    return box(padding=(3, 9), radius="$full", bg=color if solid else color + "26")[
        text(label, size=11, weight=600, color="#0B0D14" if solid else color)
    ]


def dot(color: str, size: int = 8) -> Element:
    return box(width=size, height=size, radius="$full", bg=color)


def progress(pct: float, color: str, height: int = 8) -> Element:
    return box(height=height, radius="$full", bg="$surface_hover")[
        box(
            width=f"{max(2.0, min(100.0, pct)):.1f}%",
            height="100%",
            radius="$full",
            gradient=(color, color + "AA", 0),
        ),
    ]


def section_title(title: str, subtitle: str | None = None) -> Element:
    return column(gap=2)[
        text(title, size=15, weight=650),
        subtitle and text(subtitle, size=12, color="$muted"),
    ]


def segmented(options: list[str], current: Signal[str]) -> Element:
    return row(padding=3, gap=2, radius="$md", bg="$surface_hover")[
        (
            box(
                key=f"seg-{opt}",
                padding=(6, 12),
                radius=9,
                bg="$surface" if current() == opt else "#00000000",
                bg_hover="$surface" if current() == opt else "$surface_pressed",
                shadow=(0, 1, 4, "$shadow") if current() == opt else None,
                on_click=lambda o=opt: current.set(o),
            )[text(opt, size=12, weight=600, color="$text" if current() == opt else "$muted")]
            for opt in options
        )
    ]


# ═══════════════════════════════════════════════════════════════════ sidebar

NAV = [
    ("resumen", "◆", "Resumen"),
    ("tablero", "▤", "Tablero"),
    ("equipo", "●", "Equipo"),
    ("ajustes", "⚙", "Ajustes"),
]


def nav_item(name: str, icon: str, label: str) -> Element:
    active = page() == name
    count = {"tablero": sum(t.status != "done" for t in tasks()), "equipo": len(TEAM)}.get(name)
    return row(
        key=f"nav-{name}",
        padding=(9, 12),
        gap=10,
        radius="$md",
        align="center",
        bg="$surface_pressed" if active else "#00000000",
        bg_hover="$surface_pressed" if active else "$surface_hover",
        on_click=lambda: page.set(name),
    )[
        text(icon, size=13, color="$primary" if active else "$muted"),
        text(label, size=14, weight=600 if active else 500, color="$text" if active else "$muted"),
        spacer(),
        count is not None and pill(str(count), "#7C5CFF"),
    ]


def sidebar() -> Element:
    me = TEAM[0]
    return column(width=236, padding=(22, 16), gap=4, bg="$surface")[
        row(gap=10, align="center", padding=(0, 6))[
            box(
                width=32,
                height=32,
                radius=10,
                align="center",
                justify="center",
                gradient=("#7C5CFF", "#22D3B6", 45),
                shadow=(0, 4, 14, "$glow"),
            )[text("A", size=16, weight=800, color="#FFFFFF")],
            column(gap=0)[
                text("Aurora Studio", size=15, weight=700),
                text("Workspace personal", size=11, color="$muted"),
            ],
        ],
        box(height=18),
        text("NAVEGACIÓN", size=10, weight=700, color="$muted", letter_spacing=1.2, padding=(0, 12)),
        box(height=4),
        [nav_item(*n) for n in NAV],
        spacer(),
        button(
            lambda: "☀  Tema claro" if theme() is MIDNIGHT else "☾  Tema oscuro",
            toggle_theme,
            variant="soft",
            key="theme-toggle",
            tooltip="También en Ajustes",
        ),
        box(height=8),
        row(gap=10, align="center", padding=10, radius="$md", border_width=1, border_color="$border")[
            avatar(me, 34),
            column(gap=1, grow=1, shrink=1)[
                text(me.name, size=13, weight=600, max_lines=1),
                text(me.role, size=11, color="$muted", max_lines=1),
            ],
        ],
    ]


# ═══════════════════════════════════════════════════════════════════ resumen


def bar_chart() -> Element:
    values = WEEKS[week()]
    peak = max(values)
    sel = selected_day()
    bars = []
    for i, (day, v) in enumerate(zip(DAYS, values, strict=True)):
        chosen = i == sel
        bars.append(
            column(
                key=f"bar-{i}",
                grow=1,
                width=0,
                gap=8,
                align="center",
                justify="end",
                padding=(6, 0),
                radius="$sm",
                bg="$surface_hover" if chosen else "#00000000",
                bg_hover="$surface_hover",
                on_click=lambda i=i: selected_day.set(None if selected_day() == i else i),
            )[
                text(str(v), size=11, weight=700, color="$text" if chosen else "$muted"),
                box(
                    width=26,
                    height=max(6, 118 * v / peak),
                    radius=7,
                    gradient=("#7C5CFF", "#22D3B6", 90) if chosen else ("#7C5CFF99", "#7C5CFF44", 90),
                ),
                text(day, size=11, weight=600 if chosen else 500, color="$text" if chosen else "$muted"),
            ]
        )
    total = sum(values)
    detail = (
        f"{DAYS[sel]}: {values[sel]} tareas cerradas · {values[sel] / total:.0%} de la semana"
        if sel is not None
        else "Haz clic en una barra para ver el detalle del día"
    )
    return card(grow=2, width=0, gap=16)[
        row(align="center")[
            section_title("Tareas completadas", f"{total} en total · pico de {peak} en un día"),
            spacer(),
            segmented(list(WEEKS), week),
        ],
        row(gap=6, height=170, align="end")[bars],
        row(gap=8, align="center", padding=(10, 12), radius="$sm", bg="$surface_hover")[
            dot("#22D3B6" if sel is not None else "$muted"),
            text(detail, size=12, color="$muted"),
        ],
    ]


def projects_card(ts: tuple[Task, ...]) -> Element:
    rows = []
    for name, color in PROJECTS.items():
        own = [t for t in ts if t.project == name]
        done = sum(t.points for t in own if t.status == "done")
        total = sum(t.points for t in own) or 1
        pct = 100 * done / total
        rows.append(
            column(gap=8)[
                row(gap=8, align="center")[
                    dot(color),
                    text(name, size=13, weight=600),
                    spacer(),
                    text(f"{pct:.0f}%", size=13, weight=700),
                ],
                progress(pct, color),
                text(f"{done} de {total} pts · {len(own)} tareas", size=11, color="$muted"),
            ]
        )
    return card(grow=1, width=0, gap=18)[
        section_title("Progreso por proyecto", "Ponderado por story points"),
        rows,
    ]


def activity_card(ts: tuple[Task, ...]) -> Element:
    recent = sorted(ts, key=lambda t: (t.status != "doing", -t.id))[:3]
    return card(gap=4)[
        row(align="center", padding=(0, 0, 8, 0))[
            section_title("En foco", "Lo que está en curso y lo último que entró"),
            spacer(),
            button("Ver tablero →", lambda: page.set("tablero"), variant="ghost", key="goto-board"),
        ],
        [
            row(
                key=f"act-{t.id}",
                gap=12,
                align="center",
                padding=(10, 10),
                radius="$sm",
                bg="#00000000",
                bg_hover="$surface_hover",
                on_click=lambda: page.set("tablero"),
            )[
                avatar(t.assignee, 30),
                column(gap=2, grow=1, shrink=1, width=0)[
                    text(t.title, size=13, weight=600, max_lines=1),
                    text(f"{t.project} · {t.assignee.split()[0]}", size=11, color="$muted"),
                ],
                pill(
                    next(lbl for s, lbl, _ in STATUSES if s == t.status),
                    next(c for s, _, c in STATUSES if s == t.status),
                ),
            ]
            for t in recent
        ],
    ]


def overview() -> Element:
    ts = tasks()
    done = [t for t in ts if t.status == "done"]
    doing = [t for t in ts if t.status == "doing"]
    pts_done = sum(t.points for t in done)
    pts_total = sum(t.points for t in ts) or 1
    return column(gap=18)[
        row(gap=16)[
            stat("TAREAS ACTIVAS", str(len(ts) - len(done)), f"{len(ts)} total"),
            stat("EN CURSO", str(len(doing)), f"{sum(t.points for t in doing)} pts"),
            stat("COMPLETADO", f"{100 * pts_done / pts_total:.0f}%", f"{pts_done} pts"),
            stat(
                "PRIORIDAD ALTA",
                str(sum(t.priority == "alta" and t.status != "done" for t in ts)),
                "pendientes",
                positive=False,
            ),
        ],
        row(gap=16, align="stretch")[bar_chart(), projects_card(ts)],
        activity_card(ts),
    ]


# ═══════════════════════════════════════════════════════════════════ tablero


def small_action(
    label: str, on_click, *, key: str, color: str = "$muted", enabled: bool = True, tip: str | None = None
) -> Element:
    return box(
        key=key,
        padding=(5, 9),
        radius=8,
        bg="#00000000",
        bg_hover="$surface_pressed",
        bg_pressed="$border",
        press_scale=0.92,
        opacity=1.0 if enabled else 0.3,
        on_click=on_click if enabled else None,
        tooltip=tip if enabled else None,
    )[text(label, size=12, weight=600, color=color)]


def task_card(t: Task, col_index: int) -> Element:
    pcolor = PROJECTS[t.project]
    return card(key=f"task-{t.id}", padding=14, gap=10, radius=14, shadow=(0, 4, 14, "$shadow"))[
        row(gap=6, align="center")[
            dot(pcolor, 7),
            text(t.project, size=11, weight=600, color="$muted"),
            spacer(),
            pill(t.priority, PRIORITY_COLORS[t.priority]),
        ],
        text(t.title, size=13, weight=600, line_height=1.35, max_lines=2),
        row(gap=8, align="center")[
            pill(f"#{t.tag}", "#8A91A8"),
            text(f"{t.points} pts", size=11, color="$muted"),
            spacer(),
            avatar(t.assignee, 24, tooltip=t.assignee),
        ],
        box(height=1, bg="$border"),
        row(gap=2, align="center")[
            small_action(
                "←", lambda: move(t.id, -1), key=f"l-{t.id}", enabled=col_index > 0, tip="Mover atrás"
            ),
            small_action(
                "→", lambda: move(t.id, +1), key=f"r-{t.id}", enabled=col_index < 2, tip="Mover adelante"
            ),
            spacer(),
            small_action("Eliminar", lambda: modal.set(("delete", t.id)), key=f"d-{t.id}", color="$danger"),
        ],
    ]


def tag_chip(tag: str) -> Element:
    on = tag in active_tags()
    return row(
        key=f"tag-{tag}",
        gap=6,
        align="center",
        padding=(6, 12),
        radius="$full",
        bg="$primary" if on else "$surface",
        bg_hover="$primary_hover" if on else "$surface_hover",
        border_width=1,
        border_color="$primary" if on else "$border",
        press_scale=0.95,
        on_click=lambda: toggle_tag(tag),
    )[
        text("✓" if on else "+", size=11, weight=700, color="#FFFFFF" if on else "$muted"),
        text(tag, size=12, weight=600, color="#FFFFFF" if on else "$text"),
    ]


def board() -> Element:
    tags = active_tags()
    q = query().strip().lower()
    visible = [t for t in tasks() if (not tags or t.tag in tags) and q in t.title.lower()]
    columns = []
    for i, (status, label, color) in enumerate(STATUSES):
        items = [t for t in visible if t.status == status]
        columns.append(
            column(grow=1, width=0, gap=12, padding=12, radius=18, bg="$surface_hover")[
                row(gap=8, align="center", padding=(2, 4))[
                    dot(color),
                    text(label, size=13, weight=700),
                    pill(str(len(items)), color),
                    spacer(),
                    text(f"{sum(t.points for t in items)} pts", size=11, color="$muted"),
                ],
                [task_card(t, i) for t in items]
                or column(
                    padding=(28, 12), align="center", radius=14, border_width=1, border_color="$border"
                )[text("Sin tareas aquí", size=12, color="$muted"),],
            ]
        )
    return column(gap=16)[
        row(gap=8, align="center", wrap=True)[
            text_input(query, placeholder="Buscar tareas…", key="search", width=220),
            text("Filtrar:", size=12, weight=600, color="$muted", padding=(0, 0, 0, 8)),
            [tag_chip(tag) for tag in TAGS],
            tags and small_action("Limpiar", lambda: active_tags.set(frozenset()), key="clear-tags"),
            spacer(),
            text(f"{len(visible)} de {len(tasks())} tareas", size=12, color="$muted"),
        ],
        row(gap=14, align="start")[columns],
    ]


# ════════════════════════════════════════════════════════════════════ equipo


def member_card(m: Member) -> Element:
    own = [t for t in tasks() if t.assignee == m.name and t.status != "done"]
    load = sum(t.points for t in own)
    pct = 100 * load / m.capacity
    color = "#F87171" if pct > 90 else "#F59E0B" if pct > 65 else "#34D399"
    followed = m.name in following()
    return card(width=268, gap=14, key=f"member-{m.name}")[
        row(gap=12, align="center")[
            avatar(m, 48),
            column(gap=2, grow=1, shrink=1)[
                text(m.name, size=15, weight=700, max_lines=1),
                text(m.role, size=12, color="$muted", max_lines=1),
            ],
        ],
        column(gap=8)[
            row(align="center")[
                text("Carga actual", size=12, color="$muted"),
                spacer(),
                text(f"{load}/{m.capacity} pts", size=12, weight=700, color=color),
            ],
            progress(pct, color, 6),
        ],
        row(gap=8)[
            pill(f"{len(own)} activas", m.color),
            pill(f"{sum(t.priority == 'alta' for t in own)} alta prio", "#F87171"),
        ],
        button(
            "✓ Siguiendo" if followed else "Seguir",
            lambda: toggle_follow(m.name),
            variant="soft" if followed else "primary",
            key=f"follow-{m.name}",
        ),
    ]


def team() -> Element:
    return column(gap=16)[
        text(f"Sigues a {len(following())} de {len(TEAM)} personas", size=12, color="$muted"),
        row(gap=16, wrap=True)[[member_card(m) for m in TEAM]],
    ]


# ═══════════════════════════════════════════════════════════════════ ajustes


def setting_row(title: str, description: str, control: Element) -> Element:
    return row(gap=16, align="center")[
        column(gap=2, grow=1, shrink=1)[
            text(title, size=14, weight=600),
            text(description, size=12, color="$muted"),
        ],
        control,
    ]


def settings() -> Element:
    general = card(gap=16)[
        setting_row(
            "Tema oscuro",
            "Cambia toda la interfaz al instante",
            switch(
                theme() is MIDNIGHT,
                on_change=lambda on: theme.set(MIDNIGHT if on else DAYLIGHT),
                key="set-dark",
            ),
        ),
        divider(),
        setting_row(
            "Idioma",
            "Para fechas y notificaciones",
            select(
                language,
                [("es", "Español"), ("en", "English"), ("pt", "Português")],
                key="set-lang",
                width=200,
            ),
        ),
        divider(),
        column(gap=8)[
            text("Firma de los comentarios", size=14, weight=600),
            textarea(signature, placeholder="Se añade al final de tus comentarios…", key="set-signature"),
            text(lambda: f"{len(signature())} caracteres", size=11, color="$muted"),
        ],
    ]
    notifications = card(gap=14)[
        checkbox(weekly_digest, "Resumen semanal por email", key="set-weekly"),
        checkbox(notify_assigned, "Avisarme cuando me asignan una tarea", key="set-assigned"),
        checkbox(notify_mentions, "Avisarme cuando me mencionan", key="set-mentions"),
    ]
    return column(gap=18, max_width=680)[
        tabs([("general", "General"), ("notificaciones", "Notificaciones")], settings_tab, key="set-tabs"),
        general if settings_tab() == "general" else notifications,
    ]


# ═════════════════════════════════════════════════════════════════ overlays


def modal_layer() -> Element | None:
    state = modal()
    if state is None:
        return None
    if state[0] == "new":

        def field(label: str, control: Element, **style) -> Element:
            return column(gap=6, **style)[text(label, size=12, weight=600, color="$muted"), control]

        def half(label: str, control: Element) -> Element:
            # Dos campos por fila a partes iguales.
            return field(label, control, grow=1, width=0)

        body = [
            column(gap=2)[
                text("Nueva tarea", size=17, weight=700),
                text("Enter para crear · Esc para cancelar", size=12, color="$muted"),
            ],
            field(
                "Título",
                text_input(
                    new_title,
                    placeholder="¿Qué hay que hacer?",
                    key="new-title",
                    autofocus=True,
                    on_submit=create_task,
                ),
            ),
            row(gap=12)[
                half("Proyecto", select(new_project, list(PROJECTS), key="new-project")),
                half("Prioridad", select(new_priority, ["alta", "media", "baja"], key="new-priority")),
            ],
            row(gap=12)[
                half("Etiqueta", select(new_tag, TAGS, key="new-tag")),
                half("Responsable", select(new_assignee, [m.name for m in TEAM], key="new-assignee")),
            ],
            row(gap=10, justify="end")[
                button("Cancelar", lambda: modal.set(None), variant="soft", key="m-cancel"),
                button("Crear tarea", create_task, key="m-create"),
            ],
        ]
    elif state[0] == "delete":
        t = next(t for t in tasks() if t.id == state[1])
        body = [
            row(gap=12, align="center")[
                box(width=40, height=40, radius=12, bg="#F8717126", align="center", justify="center")[
                    text("!", size=20, weight=800, color="$danger"),
                ],
                column(gap=2)[
                    text("¿Eliminar esta tarea?", size=17, weight=700),
                    text("Esta acción no se puede deshacer.", size=12, color="$muted"),
                ],
            ],
            row(gap=10, align="center", padding=12, radius="$md", bg="$surface_hover")[
                dot(PROJECTS[t.project]),
                text(t.title, size=13, weight=600, max_lines=2, grow=1, shrink=1, width=0),
            ],
            row(gap=10, justify="end")[
                # En un borrado, el foco empieza en la opción segura.
                button("Cancelar", lambda: modal.set(None), variant="soft", key="m-cancel", autofocus=True),
                button(
                    "Eliminar",
                    confirm_delete,
                    key="m-confirm",
                    bg="$danger",
                    bg_hover="#FB8A8A",
                    bg_pressed="#E05A5A",
                    shadow=(0, 6, 18, "#F8717140"),
                ),
            ],
        ]
    else:
        features = [
            "Layout flexbox con Taffy y texto con shaping real (Skia)",
            "Scroll, teclado y foco, campos de texto con IME e imágenes",
            "Hover/pressed y tooltips animados en Rust, sin pasar por Python",
            "Estado con Signals y tema claro/oscuro reactivo",
        ]
        body = [
            row(gap=12, align="center")[
                box(
                    width=44,
                    height=44,
                    radius=13,
                    align="center",
                    justify="center",
                    gradient=("#7C5CFF", "#22D3B6", 45),
                )[text("A", size=20, weight=800, color="#FFFFFF")],
                column(gap=2)[
                    text("Aurora Studio", size=18, weight=700),
                    text("Demo de capacidades · v0.2", size=12, color="$muted"),
                ],
            ],
            column(gap=10)[
                [
                    row(gap=10, align="center")[dot("#22D3B6", 6), text(f, size=13, color="$muted")]
                    for f in features
                ]
            ],
            row(justify="end")[button("Entendido", lambda: modal.set(None), key="m-ok")],
        ]
    return box(
        key="backdrop",
        position="absolute",
        top=0,
        left=0,
        right=0,
        bottom=0,
        bg="#05060ACC",
        align="center",
        justify="center",
        on_click=lambda: modal.set(None),
    )[card(width=440, padding=24, gap=20, capture=True, shadow=(0, 24, 60, "#00000088"))[body]]


def toast_layer() -> Element | None:
    msg = toast()
    if msg is None:
        return None
    return row(
        key="toast",
        position="absolute",
        right=24,
        bottom=24,
        max_width=420,
        gap=12,
        align="center",
        padding=(12, 14, 12, 16),
        radius="$md",
        bg="$surface",
        border_width=1,
        border_color="$border",
        shadow=(0, 12, 32, "$shadow"),
        on_click=lambda: toast.set(None),
    )[
        dot("#22D3B6"),
        text(msg, size=13, weight=500, shrink=1, max_lines=1),
        text("✕", size=12, color="$muted"),
    ]


# ═══════════════════════════════════════════════════════════════════════ app

PAGES = {
    "resumen": ("Resumen", "Cómo va todo de un vistazo", overview),
    "tablero": ("Tablero", "Mueve tareas entre columnas o filtra por etiqueta", board),
    "equipo": ("Equipo", "Carga de trabajo y personas que sigues", team),
    "ajustes": ("Ajustes", "Preferencias de la cuenta y notificaciones", settings),
}


def on_key(e: KeyEvent) -> bool | None:
    """Atajos globales: Esc cierra el modal y Ctrl/Cmd+N abre el formulario de nueva tarea."""
    if e.matches("escape") and modal() is not None:
        modal.set(None)
        return True
    if e.matches("mod+n"):
        open_new_task()
        return True
    return None


def view() -> Element:
    title, subtitle, render = PAGES[page()]
    return row(on_key=on_key)[
        sidebar(),
        column(grow=1, width=0, padding=(26, 0, 0, 0), gap=22)[
            row(gap=10, align="center", padding=(0, 30))[
                column(gap=3)[
                    text(title, size=26, weight=750, letter_spacing=-0.5),
                    text(subtitle, size=13, color="$muted"),
                ],
                spacer(),
                badge(lambda: f"{sum(t.status == 'doing' for t in tasks())} en curso"),
                button("Acerca de", lambda: modal.set(("about",)), variant="ghost", key="about"),
                button("+ Nueva tarea", open_new_task, key="add", tooltip="Ctrl+N"),
            ],
            # Cada página conserva su propia posición de desplazamiento.
            # El relleno va dentro para que el contenido llegue al borde de la ventana
            # y las sombras de las tarjetas no se recorten.
            scroll(key=f"page-{page()}", padding=(0, 30, 26, 30))[render()],
        ],
        modal_layer(),
        toast_layer(),
    ]


app = App(view, title="Aurora Studio", size=(1280, 820), theme=theme)


def render_gallery(out: Path) -> None:
    """Renderiza varias pantallas/estados sin ventana (útil como test de snapshot)."""
    out.mkdir(parents=True, exist_ok=True)
    shots = [
        ("1-resumen", lambda: None),
        ("2-tablero", lambda: (page.set("tablero"), move(2, +1), toggle_tag("backend"))),
        ("3-modal", lambda: modal.set(("delete", 5))),
        (
            "4-equipo-claro",
            lambda: (modal.set(None), page.set("equipo"), toggle_theme(), toggle_follow("Lucas Martins")),
        ),
        (
            "5-nueva-tarea",
            lambda: (
                toggle_theme(),
                page.set("tablero"),
                open_new_task(),
                new_title.set("Revisar accesibilidad"),
            ),
        ),
        ("6-ajustes", lambda: (modal.set(None), page.set("ajustes"), signature.set("— Raidel"))),
    ]
    for name, mutate in shots:
        mutate()
        app.render_png(str(out / f"{name}.png"), scale=1.5)
        print("✓", out / f"{name}.png")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--png":
        # Consolas sin UTF-8 (cp1252 en Windows): que "✓" no rompa la salida.
        if isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout.reconfigure(errors="replace")
        render_gallery(Path(sys.argv[2]))
    else:
        app.run()
