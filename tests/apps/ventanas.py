"""Una app con dos ventanas, para `--window`."""

from aurora import App, button, column, text

app = App(lambda: column(padding=16)[text("Principal", key="main-title")], title="Principal", size=(300, 200))


def settings():
    return column(padding=16)[
        text("Ajustes", key="settings-title"),
        button("Cerrar", lambda: None, key="close"),
    ]


app.window(settings, title="Ajustes", size=(240, 160))

if __name__ == "__main__":
    app.run()
