"""Arranque de una app típica: desde `import aurora` hasta su primer frame pintado.

Lo lanza `run.py` en un proceso nuevo por muestra (un `import` repetido en el mismo proceso no
cuesta nada) y lee la línea JSON que imprime. Usa el piloto headless: corre en CI sin ventana.
El arranque del intérprete no cuenta: el reloj empieza justo antes del `import`.

    uv run benchmarks/startup.py
"""

# ruff: noqa: E402  (los imports van después de poner en marcha el reloj)

import json
import time

start = time.perf_counter()

import aurora  # noqa: F401  (lo que se mide)

imported = time.perf_counter()

from aurora import (
    App,
    Signal,
    badge,
    button,
    card,
    checkbox,
    column,
    divider,
    row,
    scroll,
    select,
    spacer,
    switch,
    tabs,
    text,
    text_input,
)

query = Signal("")
plan = Signal("Pro")
tab = Signal("Resumen")
notify = Signal(True)
remember = Signal(False)


def view():
    sidebar = column(width=200, gap=4, padding=12, bg="$surface")[
        text("Aurora", size=18, weight=700),
        [
            button(name, lambda: None, variant="ghost", key=f"nav-{name}")
            for name in ("Inicio", "Datos", "Ajustes")
        ],
    ]
    form = card(gap=10)[
        text("Cuenta", size=16, weight=600),
        text_input(query, placeholder="Buscar…", key="buscar"),
        select(plan, ["Gratis", "Pro", "Equipo"], key="plan"),
        row(gap=12)[checkbox(remember, "Recordarme"), switch(notify, "Avisos")],
        row(gap=8)[
            spacer(), button("Cancelar", lambda: None, variant="ghost"), button("Guardar", lambda: None)
        ],
    ]
    rows = scroll(key="filas", gap=2)[
        [
            row(key=f"fila-{i}", gap=8, padding=(6, 10), radius=6, bg_hover="$surface")[
                text(f"Pedido {1000 + i}", size=13),
                spacer(),
                badge("pagado" if i % 3 else "pendiente", tone="success" if i % 3 else "danger"),
            ]
            for i in range(100)
        ]
    ]
    return row()[
        sidebar,
        column(grow=1, gap=12, padding=20)[
            tabs(["Resumen", "Pedidos", "Equipo"], tab),
            row(gap=12)[form, column(grow=1, gap=8)[text("Pedidos", size=16, weight=600), divider(), rows]],
        ],
    ]


pilot = App(view, size=(1100, 720)).pilot()
end = time.perf_counter()
print(
    json.dumps(
        {
            "import": (imported - start) * 1000,
            "frame": (end - imported) * 1000,
            "total": (end - start) * 1000,
            "nodes": pilot.stats["nodes"],
        }
    )
)
