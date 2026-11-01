"""Una prop mal escrita: `check` debe señalar la línea del `text`."""

from aurora import App, column, text


def view():
    saludo = text("hola", colr="red")
    return column(padding=16)[saludo]


App(view).run()
