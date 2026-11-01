from aurora import DAYLIGHT, MIDNIGHT, App, Column, Signal, box, chart, column, row, stat, switch, table, text

VENTAS = [
    ("Enero", 820), ("Febrero", 640), ("Marzo", 910),
    ("Abril", 700), ("Mayo", 1080), ("Junio", 1250),
]  # fmt: skip

dark = Signal(True)
total = sum(v for _, v in VENTAS)
best = max(VENTAS, key=lambda m: m[1])[0]


def view():
    return column(padding=24, gap=20, bg="$background")[
        row(justify="between", align="center")[
            text("Ventas del semestre", size=24, weight=700),
            switch(dark, "Tema oscuro", key="theme"),
        ],
        row(gap=16)[
            box(key="total", grow=1)[stat("TOTAL", str(total))],
            box(key="average", grow=1)[stat("MEDIA MENSUAL", str(total // len(VENTAS)))],
            box(key="best", grow=1)[stat("MEJOR MES", best)],
        ],
        row(gap=16, grow=1)[
            chart([v for _, v in VENTAS], labels=[m for m, _ in VENTAS], kind="bar", key="chart", grow=1),
            table(
                [{"mes": m, "ventas": v} for m, v in VENTAS],
                [Column("mes", "Mes"), Column("ventas", "Ventas", align="end")],
                key="sales",
                width=320,
            ),
        ],
    ]


App(view, title="Ventas", size=(960, 720), theme=lambda: MIDNIGHT if dark() else DAYLIGHT).run()
