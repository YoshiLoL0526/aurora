"""Genera la identidad visual del proyecto con la propia librería.

El banner del README y el logo están dibujados por Aurora: si cambias algo del
motor de render, este script es también una prueba visual rápida.

    uv run examples/brand.py            # escribe docs/assets/*.png
"""

from pathlib import Path

from aurora import App, Element, box, button, card, column, row, spacer, text

ASSETS = Path(__file__).resolve().parent.parent / "docs" / "assets"

VIOLET, TEAL = "#7C5CFF", "#22D3B6"


def logo_mark(size: float) -> Element:
    return box(
        width=size,
        height=size,
        radius=size * 0.3,
        align="center",
        justify="center",
        gradient=(VIOLET, TEAL, 45),
        shadow=(0, size * 0.12, size * 0.4, "#7C5CFF55"),
    )[text("A", size=size * 0.52, weight=800, color="#FFFFFF")]


def chip(label: str) -> Element:
    return row(padding=(6, 12), radius=999, bg="#FFFFFF0D", border_width=1, border_color="#FFFFFF1A")[
        text(label, size=13, weight=600, color="#C9CEE0")
    ]


def code_line(*parts: tuple[str, str]) -> Element:
    return row()[[text(t, size=13, color=c, font_family="DejaVu Sans Mono") for t, c in parts]]


def mini_app() -> Element:
    kw, fn, st, mu = "#C792EA", "#82AAFF", "#C3E88D", "#7A8199"
    return column(gap=14, width=430)[
        card(padding=18, gap=6, bg="#0F1220", border_color="#232842")[
            code_line(
                ("from ", kw), ("aurora ", "#E6E8F0"), ("import ", kw), ("App, Signal, card, text", "#E6E8F0")
            ),
            box(height=6),
            code_line(("clicks ", "#E6E8F0"), ("= ", mu), ("Signal", fn), ("(0)", "#E6E8F0")),
            code_line(
                ("view ", "#E6E8F0"), ("= ", mu), ("lambda", kw), (": ", mu), ("card", fn), ("()[", "#E6E8F0")
            ),
            code_line(
                ("    text", fn),
                ("(", "#E6E8F0"),
                ("lambda", kw),
                (": ", mu),
                ('f"{clicks()} clicks"', st),
                ("),", "#E6E8F0"),
            ),
            code_line(("]", "#E6E8F0")),
            code_line(("App", fn), ("(view).", "#E6E8F0"), ("run", fn), ("()", "#E6E8F0")),
        ],
        card(padding=18, gap=12, gradient=("#1E1A3A", "#0F2A2A", 30), border_color="#2E2A55")[
            row(align="center")[
                text("Ventas del día", size=13, weight=600, color="#C9CEE0"),
                spacer(),
                text("+12,4%", size=12, weight=700, color="#34D399"),
            ],
            row(gap=6, height=64, align="end")[
                [
                    box(
                        grow=1,
                        width=0,
                        height=h,
                        radius=5,
                        gradient=(VIOLET, TEAL, 90) if i == 5 else ("#7C5CFF88", "#7C5CFF33", 90),
                    )
                    for i, h in enumerate([22, 34, 28, 46, 38, 62, 30])
                ]
            ],
            row(gap=8)[button("Exportar", variant="soft", grow=1), button("Compartir", grow=1)],
        ],
    ]


def banner() -> Element:
    return row(padding=(56, 64), gap=48, align="center", bg="#0B0D14")[
        column(gap=22, grow=1, width=0)[
            row(gap=16, align="center")[
                logo_mark(64),
                text("Aurora", size=52, weight=800, letter_spacing=-1.5, color="#FFFFFF"),
            ],
            text(
                "Interfaces de escritorio profesionales en Python.",
                size=30,
                weight=700,
                letter_spacing=-0.6,
                color="#E6E8F0",
                line_height=1.2,
            ),
            text(
                "Declarativas, reactivas y elegantes por defecto. Escribes Python; "
                "un núcleo nativo en Rust se encarga del layout, el render y las animaciones.",
                size=17,
                color="#8A91A8",
                line_height=1.5,
            ),
            row(gap=8, wrap=True)[
                [chip(c) for c in ["Python 3.10+", "Rust", "Skia", "Taffy", "Sin WebView"]]
            ],
        ],
        mini_app(),
    ]


def logo() -> Element:
    return box(align="center", justify="center", bg="#00000000")[logo_mark(176)]


if __name__ == "__main__":
    ASSETS.mkdir(parents=True, exist_ok=True)
    App(banner).render_png(str(ASSETS / "banner.png"), size=(1280, 520), scale=2)
    App(logo).render_png(str(ASSETS / "logo.png"), size=(256, 256), scale=2)
    print("✓", ASSETS / "banner.png")
    print("✓", ASSETS / "logo.png")
