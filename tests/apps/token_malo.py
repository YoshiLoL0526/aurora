"""App con un token de tema mal escrito: falla al serializar, lejos de la línea que lo escribió."""

from aurora import App, column, text


def view():
    titulo = text("hola", color="$fg")
    return column(padding=16, bg="$bg")[titulo]


App(view).run()
