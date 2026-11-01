from aurora import App, Signal, button, card, column, field, text, text_input

email = Signal("")
password = Signal("")
error = Signal("")
user = Signal("")


def submit() -> None:
    if "@" not in email():
        error.set("Email inválido")
    elif len(password()) < 6:
        error.set("Contraseña demasiado corta")
    else:
        error.set("")
        user.set(email())


def view():
    if user():
        return column(padding=32, align="center", justify="center")[
            text(f"Bienvenido, {user()}", size=20, weight=700)
        ]
    return column(padding=32, align="center", justify="center")[
        card(padding=24, gap=16, width=360)[
            text("Iniciar sesión", size=22, weight=700),
            field(text_input(email, placeholder="ana@ejemplo.com", key="email"), label="Correo"),
            field(
                text_input(password, placeholder="Mínimo 6 caracteres", key="password"), label="Contraseña"
            ),
            error() and text(error(), color="$danger"),
            button("Entrar", submit, key="submit"),
        ]
    ]


App(view, title="Acceso", size=(480, 520)).run()
