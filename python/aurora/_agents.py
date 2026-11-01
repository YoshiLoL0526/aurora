"""`aurora agents`: la sección de `AGENTS.md` que explica Aurora a un agente de programación.

La sección va entre marcas para poder actualizarla al cambiar de versión sin tocar el resto del
archivo: si el proyecto ya tiene un `AGENTS.md`, se añade al final (o se sustituye la anterior).
"""

from __future__ import annotations

from pathlib import Path

START = "<!-- aurora:inicio (generado por `aurora agents`; se actualiza al volver a ejecutarlo) -->"
END = "<!-- aurora:fin -->"

# Comandos con los que un agente comprueba su trabajo desde la terminal (salen en la sección).
CHECK_COMMANDS: list[tuple[str, str]] = [
    (
        "aurora check app.py",
        "construye y pinta un frame; si falla, dice el archivo y la línea de tu código. Lista los "
        "avisos de layout (texto que no cabe, controles fuera de la ventana o sin nombre); "
        "`--strict` los hace fallar",
    ),
    (
        "aurora shot app.py -o captura.png",
        "renderiza la app a PNG sin ventana (`--key K` recorta a un nodo, `--scale 2`, "
        "`--theme light`): mírala para revisar el diseño",
    ),
    (
        "aurora tree app.py",
        "el árbol pintado en texto (rol, texto, `#key`, caja y estados) y los avisos; úsalo para "
        "encontrar las keys",
    ),
    (
        'aurora pilot app.py "click guardar; type hola; press enter; expect text hola; shot s.png"',
        "interacción guionizada; se para en el paso que falla y sugiere keys parecidas "
        "(`aurora pilot --help` tiene la gramática)",
    ),
]


def section(version: str) -> str:
    """La sección de Aurora para `AGENTS.md`, con sus marcas."""
    lines = [
        START,
        "## Aurora (interfaz de escritorio)",
        "",
        f"Este proyecto usa Aurora {version} (`aurora-ui`), una librería de UI de escritorio",
        "declarativa y reactiva en Python. Es reciente y no está en tus datos de entrenamiento: no",
        "supongas APIs de otras librerías (React, Flet, Tkinter, Qt, CSS). Antes de escribir código,",
        "lee la documentación de la versión instalada:",
        "",
        "- `aurora docs`: chuleta con el modelo mental, las firmas, las props de estilo, los tokens",
        "  y los errores frecuentes. Léela entera antes de empezar.",
        "- `aurora docs <tema>`: una sección de la referencia (`aurora docs button`,",
        "  `aurora docs pilot`, `aurora docs style`).",
        "- `aurora docs --search <texto>`: busca en la guía, las recetas y la referencia.",
        "- `aurora docs --full`: toda la documentación en Markdown.",
        "",
        "### Comprobar el trabajo",
        "",
        "Sin abrir ventanas (`app.run()` bloquea; no lo llames en tests):",
        "",
        '- `App(view, size=(900, 600)).render_png("captura.png")` dibuja la vista igual que la',
        "  ventana: mira la captura para revisar el diseño.",
        '- `pilot = App(view).pilot()` simula al usuario por `key`: `pilot.click("guardar")`,',
        '  `pilot.type("hola")`, `pilot.press("enter")`, `pilot.settle()`, `pilot.a11y_tree()`.',
        "  Escribe tests con pytest así (`aurora docs pilot`).",
        "- Una prop o un token mal escritos lanzan `TypeError` o `ThemeTokenError` al construir la",
        "  vista, con la sugerencia correcta: léela en vez de adivinar.",
    ]
    if CHECK_COMMANDS:
        lines += ["", "Desde la terminal:", ""]
        lines += [f"- `{command}`: {what}" for command, what in CHECK_COMMANDS]
    lines += [END]
    return "\n".join(lines) + "\n"


def write(path: Path, version: str, *, force: bool = False) -> str:
    """Escribe la sección en `path`. Devuelve qué hizo: `"creado"`, `"actualizado"` (había una
    sección de Aurora y se sustituye), `"añadido"` (al final de un archivo existente) o
    `"sobrescrito"` (con `force`, el archivo entero)."""
    new = section(version)
    if force or not path.exists():
        action = "sobrescrito" if path.exists() else "creado"
        path.write_text(f"# AGENTS.md\n\n{new}", encoding="utf-8", newline="\n")
        return action
    text = path.read_text(encoding="utf-8")
    start, end = text.find(START), text.find(END)
    if start != -1 and end > start:
        text = text[:start] + new.rstrip("\n") + text[end + len(END) :]
        action = "actualizado"
    else:
        text = text.rstrip("\n") + "\n\n" + new if text.strip() else new
        action = "añadido"
    path.write_text(text, encoding="utf-8", newline="\n")
    return action
