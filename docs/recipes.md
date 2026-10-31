# Recetas

Soluciones cortas para tareas habituales. Cada receta es un programa completo (o casi) que puedes
copiar y adaptar; las que llevan captura se ejecutan al construir esta documentación, así que
funcionan con la versión publicada. Para el porqué de cada pieza, la [guía](guide.md) y la
[referencia](reference.md).

## Formulario con validación

Valida mientras se escribe, pero no regañes antes de tiempo: los errores aparecen cuando el
usuario intenta enviar (o ya ha escrito algo). `field` pone la etiqueta, la ayuda y el error, y el
botón se desactiva mientras el formulario no es válido.

```python live size=420x330
from aurora import App, Signal, button, card, column, field, text, text_input

nombre = Signal("")
correo = Signal("")
intentado = Signal(False)
enviado = Signal(None)


def errores() -> dict[str, str]:
    e = {}
    if not nombre().strip():
        e["nombre"] = "Escribe tu nombre"
    if "@" not in correo() or "." not in correo().split("@")[-1]:
        e["correo"] = "Ese correo no parece válido"
    return e


def enviar(_texto=None):
    intentado.set(True)
    if not errores():
        enviado.set(nombre())


def view():
    # Un campo vacío no es un error hasta que se intenta enviar.
    e = {k: v for k, v in errores().items() if intentado() or (nombre() if k == "nombre" else correo())}
    return column(padding=20)[
        card(gap=12)[
            field(
                text_input(nombre, placeholder="Ada Lovelace", key="nombre"),
                label="Nombre",
                error=e.get("nombre"),
            ),
            field(
                text_input(correo, placeholder="ada@ejemplo.com", on_submit=enviar, key="correo"),
                label="Correo",
                hint="Solo para avisarte",
                error=e.get("correo"),
            ),
            button("Crear cuenta", enviar, key="enviar"),
            enviado() and text(f"¡Hola, {enviado()}!", color="$success"),
        ]
    ]


correo.set("ada@")  # oculto
App(view, size=(420, 330)).run()
```

## Carga asíncrona con spinner

`app.spawn` ejecuta una corrutina en un bucle `asyncio` en segundo plano; asignar un `Signal` desde
ella repinta la ventana sola. La vista solo mira el estado: cargando, error o datos.

```python live size=420x150
import asyncio

from aurora import App, Signal, button, column, row, spinner, text

estado = Signal("inicio")  # "inicio" | "cargando" | "listo" | "error"
datos = Signal(())


async def cargar() -> None:
    estado.set("cargando")
    try:
        await asyncio.sleep(1.5)  # aquí iría tu petición (httpx, aiohttp…)
        datos.set(("Pedido 1041", "Pedido 1042", "Pedido 1043"))
        estado.set("listo")
    except Exception:
        estado.set("error")


def view():
    cuerpo = {
        "inicio": text("Sin datos todavía", color="$muted"),
        "cargando": row(gap=10, align="center")[spinner(), text("Cargando pedidos…", color="$muted")],
        "error": text("No se pudo cargar", color="$danger"),
        "listo": column(gap=4)[[text(d) for d in datos()]],
    }[estado()]
    return column(padding=20, gap=14)[
        estado() != "cargando" and button("Cargar", lambda: app.spawn(cargar()), key="cargar"),
        cuerpo,
    ]


app = App(view, size=(420, 150), motion=False)  # sin movimiento: el spinner queda fijo en la captura
estado.set("cargando")  # oculto
app.run()
```

Si la carga es CPU (procesar un archivo grande), usa un hilo (`threading.Thread`) o
`asyncio.to_thread` dentro de la corrutina: el bucle de la ventana no se bloquea en ningún caso.

## Lista grande filtrable

`virtual_list` solo construye las filas visibles, así que filtrar 50 000 elementos en cada tecla
cuesta lo que la comprensión de Python, no lo que pintar 50 000 filas. Con filas `@component`, una
fila que no cambia ni siquiera se vuelve a construir.

```python live size=420x300
from aurora import App, Signal, column, component, row, spacer, text, text_input, virtual_list

PRODUCTOS = [f"{('Tornillo', 'Tuerca')[n % 2]} {n:05d}" for n in range(50_000)]
filtro = Signal("")


@component
def fila(nombre: str):
    return row(key=nombre, grow=1, align="center", padding=(0, 12), radius="$sm", bg_hover="$surface")[
        text(nombre), spacer(), text("en stock", size=12, color="$muted")
    ]


def view():
    q = filtro().strip().lower()
    visibles = [p for p in PRODUCTOS if q in p.lower()] if q else PRODUCTOS
    return column(padding=16, gap=10)[
        text_input(filtro, placeholder="Filtrar productos…", key="filtro"),
        text(f"{len(visibles):,} productos".replace(",", "."), size=12, color="$muted"),
        virtual_list(len(visibles), lambda i: fila(visibles[i]), item_height=34, key="productos"),
    ]


filtro.set("tuerca 001")  # oculto
App(view, size=(420, 300)).run()
```

## Maestro-detalle

Un `tree` a la izquierda, el detalle a la derecha y un `splitter` entre los dos que el usuario
arrastra. El tamaño del panel va en un `Signal`, así que puedes guardarlo con los ajustes (receta
siguiente).

```python live size=560x240
from aurora import App, Signal, column, splitter, text, tree

CARPETAS = [
    ("Clientes", [("Lucía Fernández", []), ("Marco Rossi", [])]),
    ("Proveedores", [("Aiko Tanaka", [])]),
]
elegido = Signal(("Clientes", "Lucía Fernández"))
abiertos = Signal({("Clientes",)})
ancho = Signal(200.0)


def view():
    lista = tree(
        CARPETAS,
        lambda n: n[1],
        label=lambda n: n[0],
        selected=elegido,
        expanded=abiertos,
        key="carpetas",
    )
    ruta = elegido() or ()
    detalle = column(padding=16, gap=6)[
        text(ruta[-1] if ruta else "Elige un contacto", size=18, weight=700),
        text(" › ".join(ruta), color="$muted"),
    ]
    return column(grow=1, padding=8)[splitter(lista, detalle, size=ancho, min_sizes=(140, 200))]


App(view, size=(560, 240)).run()
```

## Ajustes que se recuerdan

El tamaño y la posición de la ventana se recuerdan solos con `App(..., remember="mi-app")`. Para
el resto (tema, preferencias), guarda un JSON en el directorio de configuración del usuario al
cambiar un `Signal` y léelo al arrancar:

```python
import json
import os
from pathlib import Path

from aurora import DAYLIGHT, MIDNIGHT, App, Signal, column, switch

if os.name == "nt":
    CONFIG = Path(os.environ["APPDATA"]) / "mi-app" / "ajustes.json"
else:
    CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mi-app" / "ajustes.json"


def cargar() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}  # primera vez, o un archivo dañado: valores por defecto


ajustes = cargar()
oscuro = Signal(ajustes.get("oscuro", True))
avisos = Signal(ajustes.get("avisos", False))


def guardar(_valor=None) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"oscuro": oscuro(), "avisos": avisos()}), encoding="utf-8")


for s in (oscuro, avisos):
    s.subscribe(guardar)  # se guarda en cada cambio, venga de donde venga


def view():
    return column(padding=20, gap=12)[switch(oscuro, "Tema oscuro"), switch(avisos, "Avisos")]


App(view, theme=lambda: MIDNIGHT if oscuro() else DAYLIGHT, remember="mi-app").run()
```

## Ventana sin marco con barra propia

`decorations=False` quita el marco del sistema y `title_bar` pone una barra que mueve la ventana
(doble clic: maximizar) con los botones de siempre. Tus acciones van en `actions`; sus clics no
mueven la ventana.

```python live size=520x200
from aurora import App, button, column, text, title_bar


def view():
    return column(grow=1)[
        title_bar(
            "Informe trimestral",
            icon=text("◆", color="$primary"),
            actions=button("Compartir", variant="soft", padding=(4, 12)),
            controls="windows",
        ),
        column(grow=1, padding=20)[text("El contenido de la app va aquí.", color="$muted")],
    ]


App(view, size=(520, 200), decorations=False, min_size=(360, 160)).run()
```

Con `controls="macos"` (o en macOS, por defecto) los botones son los tres círculos a la
izquierda. Para hacer arrastrable otra zona, usa la propiedad `window_drag="move"`.

## Tablero kanban

Varias `sortable` con el mismo `group` forman un tablero: los elementos se arrastran entre listas
(o se mueven con Espacio y las flechas) y `MoveEvent.apply` hace el movimiento sobre tus datos.

```python live size=560x230 align=stretch
from aurora import App, Signal, box, column, row, sortable, text

tablero = Signal({"Pendiente": ["Diseño", "Docs"], "En curso": ["API"], "Hecho": ["Login"]})


def tarjeta(titulo: str):
    return box(padding=10, radius="$sm", bg="$surface", border_width=1, border_color="$border")[text(titulo)]


def columna(nombre: str, tareas: list[str]):
    return column(gap=8, grow=1, width=0)[
        text(f"{nombre} · {len(tareas)}", size=12, weight=700, color="$muted"),
        sortable(
            tareas,
            tarjeta,
            key=nombre,
            group="tablero",
            label=nombre,
            empty=text("Suelta aquí", size=12, color="$muted", padding=12),
            on_move=lambda e: tablero.set(e.apply(tablero())),
        ),
    ]


def view():
    return row(gap=12, padding=16, align="start")[[columna(n, t) for n, t in tablero().items()]]


App(view, size=(560, 230)).run()
```

## Chat

Mensajes de alto variable en una `virtual_list` sin `item_height`, con `stick_to_end=True`: empieza
abajo y sigue los mensajes nuevos mientras el usuario esté al final; si sube a leer, no lo
arrastra.

```python live size=420x320
from aurora import App, Signal, box, column, row, text, text_input, virtual_list

mensajes = Signal(
    (
        ("ana", "¿Subimos la versión hoy?"),
        ("tú", "Sí, en cuanto pase la CI. Me falta revisar el changelog y las capturas de la guía."),
        ("ana", "Perfecto 👍"),
        ("tú", "Listo: todo en verde."),
    )
)
borrador = Signal("")


def burbuja(i: int):
    autor, texto = mensajes()[i]
    mio = autor == "tú"
    return row(justify="end" if mio else "start", padding=(4, 12))[
        box(max_width=280, padding=(8, 12), radius=14, bg="$primary" if mio else "$surface")[
            text(texto, color="#FFFFFF" if mio else "$text")
        ]
    ]


def enviar(texto: str) -> None:
    if texto.strip():
        mensajes.set((*mensajes(), ("tú", texto.strip())))
        borrador.set("")


def view():
    return column(padding=(12, 0))[
        virtual_list(len(mensajes()), burbuja, stick_to_end=True, key="chat"),
        box(padding=(8, 12))[
            text_input(borrador, placeholder="Escribe un mensaje…", on_submit=enviar, key="msg")
        ],
    ]


App(view, size=(420, 320)).run()
```

Las filas pueden cambiar de alto (un mensaje que se edita, una imagen que carga): la lista lo
corrige sin que salte lo que se está viendo.

## Tema propio

Un `Theme` es un diccionario de colores y radios. Parte de `MIDNIGHT` o `DAYLIGHT` y cambia lo que
quieras: todos los componentes lo siguen, porque solo usan tokens (`"$primary"`, `"$surface"`…).

```python live size=420x150
from aurora import MIDNIGHT, App, Theme, badge, button, card, row, text

BOSQUE = Theme(
    colors={
        **MIDNIGHT.colors,
        "background": "#0C1410",
        "surface": "#13201A",
        "border": "#22352B",
        "primary": "#34D399",
        "primary_hover": "#4ADE80",
        "primary_pressed": "#22C55E",
        "glow": "#34D39940",
    },
    radius={**MIDNIGHT.radius, "sm": 4, "md": 6},
)


def view():
    return row(padding=20)[
        card(gap=10)[
            row(gap=8, align="center")[text("Despliegue", weight=700), badge("estable", tone="success")],
            button("Publicar", lambda: None),
        ]
    ]


App(view, size=(420, 150), theme=BOSQUE).run()
```

Para seguir el tema del sistema o dejar elegir al usuario, pasa una función:
`App(view, theme=lambda: BOSQUE if oscuro() else DAYLIGHT)`.

## Atajos de teclado globales

Un `on_key` en la raíz de la vista recibe las teclas que nadie más atendió. Devuelve `True` para
darla por atendida; `KeyEvent.matches` entiende `mod` (Ctrl, o Cmd en macOS).

```python
from aurora import App, KeyEvent, Signal, column, text

paleta = Signal(False)
guardado = Signal(0)


def on_key(e: KeyEvent):
    if e.matches("mod+k"):
        paleta.set(not paleta())
        return True
    if e.matches("mod+s"):
        guardado.update(lambda n: n + 1)
        return True
    if e.matches("escape") and paleta():
        paleta.set(False)
        return True
    return None  # el resto sigue su camino (Tab, flechas, Enter…)


def view():
    return column(padding=20, gap=8, grow=1, on_key=on_key)[
        text("Ctrl+K: paleta de comandos · Ctrl+S: guardar", color="$muted"),
        paleta() and text("Paleta abierta", weight=700),
        text(f"Guardado {guardado()} veces"),
    ]


App(view).run()
```

Un atajo que debe funcionar también cuando el foco está en un campo de texto (que se queda las
teclas que escribe) va mejor en la barra de menús: `menus.item("Guardar", guardar,
shortcut="mod+s")`.

## Probar una app con `Pilot`

`app.pilot()` ejecuta la app sin ventana con el mismo runtime: hace clic por `key`, escribe,
pulsa teclas, arrastra y lee el árbol de accesibilidad. Con pytest, cada test empieza de un estado
limpio si el estado vive en una función que crea la app:

```python
# app.py
from aurora import App, Signal, button, column, text


def crear_app() -> App:
    cuenta = Signal(0)

    def view():
        return column(padding=20, gap=8)[
            text(f"Clics: {cuenta()}", key="cuenta"),
            button("Sumar", lambda: cuenta.update(lambda n: n + 1), key="sumar"),
        ]

    return App(view, size=(300, 160))


if __name__ == "__main__":
    crear_app().run()
```

```python
# test_app.py
from app import crear_app


def nodo(pilot, key):
    return next(n for n in pilot.a11y_tree() if n["key"] == key)


def test_sumar_con_el_raton_y_con_el_teclado():
    pilot = crear_app().pilot()
    pilot.click("sumar")
    assert nodo(pilot, "cuenta")["value"] == "Clics: 1"  # un texto se anuncia con su valor

    pilot.focus("sumar")
    pilot.press("enter")
    assert nodo(pilot, "cuenta")["value"] == "Clics: 2"


def test_el_boton_se_anuncia_con_su_nombre():
    pilot = crear_app().pilot()
    boton = nodo(pilot, "sumar")
    assert (boton["role"], boton["label"]) == ("button", "Sumar")


def test_captura(tmp_path):
    crear_app().render_png(str(tmp_path / "app.png"))  # snapshot visual
```

`pilot.settle()` espera a que terminen las animaciones, `pilot.type("hola\n")` escribe en el campo
enfocado y `pilot.drag_to(key, destino)` arrastra. Todo lo que hace está en la
[referencia de `Pilot`](reference.md#pilot-tests-de-interacción).
