"""La vista lanza una excepción: `check` debe señalar la línea de la división."""

from aurora import App, column, text


def total(items):
    return sum(items) / len(items)


def view():
    return column(padding=16)[text(f"Media: {total([])}")]


App(view).run()
