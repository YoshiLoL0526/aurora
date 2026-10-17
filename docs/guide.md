# Guía: tu primera app con Aurora

En esta guía construimos, paso a paso, un **monitor de servicios**: una lista de servicios con su
estado, filtros, un panel de resumen, un modal de detalle y tema claro/oscuro. Por el camino
aparecen todos los conceptos importantes de Aurora.

Cada paso es un programa completo que puedes ejecutar. Si algo no queda claro, la
[referencia](reference.md) tiene el detalle de cada propiedad.

1. [Instalación](#1-instalación)
2. [Una ventana](#2-una-ventana)
3. [Layout: filas, columnas y espacio](#3-layout-filas-columnas-y-espacio)
4. [Estilo y tokens de tema](#4-estilo-y-tokens-de-tema)
5. [Estado con Signal](#5-estado-con-signal)
6. [Listas y componentes propios](#6-listas-y-componentes-propios)
7. [Filtros y valores derivados](#7-filtros-y-valores-derivados)
8. [Superposiciones: modales y toasts](#8-superposiciones-modales-y-toasts)
9. [Tema claro y oscuro](#9-tema-claro-y-oscuro)
10. [Tests sin pantalla](#10-tests-sin-pantalla)
11. [Distribuir la app](#11-distribuir-la-app)

---

## 1. Instalación

Aurora se publica en PyPI como **`aurora-ui`**. Necesitas **Python ≥ 3.11**:

```bash
pip install aurora-ui      # o, con uv en tu proyecto: uv add aurora-ui
```

Los wheels traen el núcleo nativo ya compilado para Windows, macOS (x64 y arm64) y Linux x86_64,
así que no hace falta Rust. En Linux, fontconfig y freetype (los traen casi todas las
distribuciones; en Debian/Ubuntu son `libfontconfig1` y `libfreetype6`).

Crea tu archivo `mi_app.py` con el contador de la [página principal](index.md) y ejecútalo con
`python mi_app.py` (o `uv run mi_app.py` si usas uv).

Si vas a **trabajar sobre Aurora** (o compilar para otra plataforma), clona el repositorio;
necesitarás [uv](https://docs.astral.sh/uv/) y Rust ([rustup](https://rustup.rs)), y en Linux los
paquetes de desarrollo (`libfontconfig-dev` y `libfreetype-dev`):

```bash
git clone https://github.com/YoshiLoL0526/aurora.git
cd aurora
uv sync
```

`uv sync` compila el núcleo nativo e instala Aurora en modo editable dentro de `.venv`; dentro
del repositorio, ejecuta tus scripts con `uv run mi_app.py`.

## 2. Una ventana

```python live size=640x160
from aurora import App, text


def view():
    return text("Hola, Aurora", size=32, weight=700)


App(view, title="Monitor").run()
```

Tres ideas que se mantienen durante toda la guía:

- **La vista es una función.** `view()` devuelve la descripción de la interfaz. Aurora la vuelve a
  llamar cuando algo puede haber cambiado.
- **El elemento raíz ocupa toda la ventana** y toma el fondo, el color y la fuente del tema.
- **Los tamaños son lógicos.** `size=32` se ve igual de grande en una pantalla normal y en una
  Retina.

### Más de una ventana

Para una segunda ventana (un detalle, unos ajustes, una paleta de comandos) no cambia nada del
modelo: cada ventana tiene su propia vista y todas comparten los `Signal` y el tema.

```python
app = App(monitor, title="Monitor", size=(900, 600))
detalle = app.window(detalle_view, title="Detalle del servicio", size=(420, 320))


def abrir(servicio):
    detalle.open()


def cerrar():
    detalle.close()
```

- Las ventanas creadas antes de `run()` se abren al arrancar; las creadas en marcha, al momento.
- Un `Signal` que cambie se ve en **todas** las ventanas a la vez.
- `detalle.title` y `detalle.size` se cambian en marcha, desde cualquier hilo, y `detalle.close()`
  / `.open()` la cierran y la vuelven a abrir sin perder su vista.
- `on_close` permite cancelar el cierre devolviendo `False` (útil para pedir confirmación).
- La app termina al cerrarse su última ventana; `app.quit()` la cierra desde cualquier sitio.
  La principal también es un `Window`: `app.main` (título y tamaño en marcha, cerrarla y
  reabrirla, `on_close` que confirme). `examples/windows.py`, `examples/notepad.py` y
  `examples/tray.py` enseñan las tres piezas en marcha.

### Abrir y guardar archivos

Para el botón «Abrir…» de verdad, los diálogos nativos del sistema (síncronos, con la app en
espera mientras están abiertos):

```python
from pathlib import Path

from aurora import dialogs

contenido = Signal("")


def abrir() -> None:
    ruta = dialogs.open_file(title="Abrir nota", filters=[("Texto", ["txt", "md"])])
    if ruta is not None:
        contenido.set(Path(ruta).read_text(encoding="utf-8"))


def guardar() -> None:
    ruta = dialogs.save_file(default_name="nota.txt", filters=[("Texto", ["txt"])])
    if ruta is not None:
        Path(ruta).write_text(contenido(), encoding="utf-8")
```

`dialogs.open_files()` elige varios a la vez y `dialogs.pick_folder()` una carpeta. En los tests,
sustitúyelas por un doble: `monkeypatch.setattr(dialogs, "open_file", lambda **_: "nota.txt")`.

### Bandeja del sistema

Para que la app siga disponible con la ventana cerrada —o viva solo en la bandeja—, ponele un
icono en la bandeja del sistema:

```python
from aurora import menus

app.tray(
    icon="icono.png",
    tooltip="Notas",
    menu=[
        menus.item("Abrir ventana", lambda: ventana.open()),
        menus.item("Nueva nota", nueva_nota),
        menus.separator(),
        menus.item("Salir", app.quit),
    ],
)
```

Con bandeja, la app ya no termina al cerrarse su última ventana: sigue en segundo plano hasta
`app.quit()` (o `app.tray_hide()` para volver al comportamiento normal). El menú se describe con
`menus.item(label, fn)`, `menus.separator()` y `menus.submenu(label, ...)` — la misma descripción
que usan la barra y los menús contextuales—. El icono puede ser una ruta o bytes de un PNG/SVG.
En GNOME hace falta la extensión AppIndicator para ver bandejas.

Para mostrar u ocultar la ventana desde la bandeja, `app.main` es la principal como un `Window`:
`app.main.close()` la cierra (la app sigue) y `app.main.open()` la vuelve a abrir.
`examples/tray.py` es el ejemplo completo.

### Notificaciones

Para avisar de algo cuando la ventana no está delante —o está cerrada, si vives en la bandeja—:

```python
async def generar() -> None:
    await crear_informe()
    app.notify("Informe generado", "ya está en tu carpeta de descargas")


app.spawn(generar())
```

`app.notify(title, body, icon=...)` la pinta el sistema (Windows, macOS, Linux) y funciona desde
cualquier hilo, con o sin ventana. Si el sistema no las admite, se avisa por stderr y la app sigue;
los límites por plataforma están en la [referencia](reference.md#notificaciones).

### Barra de menús

`App(view, menu=menus.bar(...))` pone la barra de menús nativa (Windows y macOS), con atajos del
sistema y entradas estándar:

```python
app = App(
    view,
    menu=menus.bar(
        menus.submenu(
            "Archivo",
            menus.item("Abrir…", abrir, shortcut="mod+o"),
            menus.separator(),
            menus.item("Salir", app.quit, shortcut="mod+q"),
        ),
        menus.submenu("Edición", menus.predefined("copy"), menus.predefined("paste")),
    ),
)
```

`shortcut` es un atajo del sistema: `"mod+s"` (`mod` es Control fuera de macOS y Comando en macOS),
`"ctrl+shift+p"`, `"f5"`… Los gestiona el sistema, así que no los repitas en `on_key`. En macOS el
núcleo añade delante el submenú estándar de la app (Acerca de, Ocultar, Salir…). En Linux no hay
barra nativa: ese hueco lo cubre el componente `menu` dentro de la interfaz.

### Menús contextuales

Cualquier elemento acepta `on_context_menu` (clic derecho): una lista de entradas o un callable
que la devuelve, que se evalúa al abrir el menú — así el menú puede depender del estado:

```python
def contexto() -> list[dict]:
    return [
        menus.item("Renombrar", renombrar),
        menus.separator(),
        menus.item("Eliminar", eliminar, enabled=hay_seleccion()),
    ]


fila = card(on_context_menu=contexto)[...]
```

Es nativo en Windows y macOS; en Linux no aparece (los menús nativos necesitan GTK).

## 3. Layout: filas, columnas y espacio

Los hijos se añaden con corchetes. `row` los coloca en horizontal y `column` en vertical:

```python live size=900x200
from aurora import App, column, row, spacer, text


def view():
    return column(padding=32, gap=16)[
        row(align="center")[
            text("Servicios", size=28, weight=700),
            spacer(),  # ocupa todo el espacio libre
            text("3 en línea", color="$muted"),
        ],
        text("Estado de la infraestructura en tiempo real.", color="$muted"),
    ]


App(view, title="Monitor", size=(900, 600)).run()
```

- `padding` es el relleno interior y `gap` la separación entre hijos.
- `align` alinea en el eje cruzado (`"center"` centra verticalmente dentro de una `row`).
- `spacer()` empuja lo que viene detrás hasta el final. Es la forma idiomática de separar
  "izquierda" y "derecha".

## 4. Estilo y tokens de tema

Los colores del tema se usan con tokens que empiezan por `$`. Así la app cambia de aspecto
completo al cambiar de tema, sin tocar la vista.

```python live size=900x220
from aurora import App, box, column, row, text


def service_row(name: str, region: str, online: bool):
    color = "$success" if online else "$danger"
    return row(
        gap=12,
        align="center",
        padding=(14, 16),
        radius="$md",
        bg="$surface",
        border_width=1,
        border_color="$border",
    )[
        box(width=10, height=10, radius="$full", bg=color),
        column(gap=2, grow=1)[
            text(name, weight=600),
            text(region, size=12, color="$muted"),
        ],
        text("En línea" if online else "Caído", size=12, weight=600, color=color),
    ]


def view():
    return column(padding=32, gap=10)[
        service_row("API pública", "us-east-1", True),
        service_row("Workers", "eu-west-1", False),
    ]


App(view, title="Monitor", size=(900, 600)).run()
```

Fíjate en que `service_row` es **una función normal de Python** que devuelve elementos. Así se
crean componentes en Aurora: sin clases, sin registros ni decoradores.

## 5. Estado con Signal

Un `Signal` guarda un valor. Léelo llamándolo (`s()`) y cámbialo con `set` o `update`. Cualquier
elemento con `on_click` se vuelve interactivo, con hover y pulsación animados de serie.

```python live size=900x200
from aurora import App, Signal, button, column, row, text

checks = Signal(0)


def view():
    return column(padding=32, gap=16)[
        text(lambda: f"Comprobaciones realizadas: {checks()}", size=20, weight=600),
        row(gap=8)[
            button("Comprobar ahora", lambda: checks.update(lambda n: n + 1)),
            button("Reiniciar", lambda: checks.set(0), variant="ghost"),
        ],
    ]


App(view, title="Monitor", size=(900, 600)).run()
```

`text(lambda: ...)` recibe una función en lugar de un string: se evalúa en cada actualización,
así el texto siempre refleja el estado actual.

## 6. Listas y componentes propios

Guarda los datos en un `Signal` y genera la lista con una comprensión normal de Python. Usa datos
**inmutables** (tuplas, dataclasses congeladas) y reemplázalos al cambiar: es más fácil de razonar
y evita errores sutiles.

```python live size=900x380
from dataclasses import dataclass, replace

from aurora import App, Signal, box, column, row, text


@dataclass(frozen=True)
class Service:
    name: str
    region: str
    online: bool
    latency_ms: int


services = Signal(
    (
        Service("API pública", "us-east-1", True, 42),
        Service("Workers", "eu-west-1", False, 0),
        Service("Base de datos", "us-east-1", True, 8),
        Service("CDN", "global", True, 15),
    )
)


def toggle(name: str):
    services.update(lambda ss: tuple(replace(s, online=not s.online) if s.name == name else s for s in ss))


def service_row(s: Service):
    color = "$success" if s.online else "$danger"
    return row(
        key=f"svc-{s.name}",  # identidad estable en listas
        gap=12,
        align="center",
        padding=(14, 16),
        radius="$md",
        bg="$surface",
        bg_hover="$surface_hover",
        border_width=1,
        border_color="$border",
        on_click=lambda: toggle(s.name),
    )[
        box(width=10, height=10, radius="$full", bg=color),
        column(gap=2, grow=1)[
            text(s.name, weight=600),
            text(s.region, size=12, color="$muted"),
        ],
        text(f"{s.latency_ms} ms" if s.online else "Caído", size=12, weight=600, color=color),
    ]


def view():
    return column(padding=32, gap=10)[
        text("Haz clic en un servicio para cambiar su estado", color="$muted"),
        [service_row(s) for s in services()],
    ]


App(view, title="Monitor", size=(900, 600)).run()
```

> **¿Por qué `key`?** Aurora conserva el estado visual de cada elemento (la transición de hover,
> por ejemplo) entre actualizaciones. En listas que cambian de orden o de tamaño, `key` le dice
> qué elemento es cuál.

Cada cambio vuelve a llamar a `view()`, y con cuatro servicios no importa. Con miles de filas sí:
marca la fila como componente y Aurora solo reconstruirá las que reciban argumentos distintos.

```python
from aurora import component


@component
def service_row(s: Service):
    return row(key=f"svc-{s.name}")[...]  # el resto de estilos e hijos, igual que antes
```

`Service` es una dataclass congelada, así que se compara por valor: al cambiar un servicio solo su
fila se reconstruye. Pasa como argumento lo que distingue a cada fila (por ejemplo,
`service_row(s, s.name == selected())`) en lugar de leer dentro un `Signal` que comparten todas:
el componente depende de los `Signal` que lee. Los detalles están en la
[referencia](reference.md#component).

Si la lista puede crecer más que la ventana, envuélvela en `scroll`. Recorta lo que no cabe y se
desplaza con la rueda, el trackpad o arrastrando su barra, que aparece al desplazarse o al acercar
el puntero al borde:

```python live continue size=900x380
from aurora import scroll


def view():
    return column(padding=32, gap=10)[
        text("Haz clic en un servicio para cambiar su estado", color="$muted"),
        scroll(key="services", gap=10)[[service_row(s) for s in services()]],
    ]
```

Un `scroll` vertical sin `height` ocupa el espacio libre de su contenedor, y sus hijos mantienen
su tamaño en lugar de encogerse para caber. Con una `key`, la posición se conserva aunque la vista
se reconstruya.

Con miles de filas, construirlas todas para ver veinte es un desperdicio. Si todas miden lo mismo,
usa `virtual_list`: solo construye las que están a la vista y las va cambiando al desplazarse.

```python live continue size=900x380
from aurora import virtual_list


def view():
    rows = services()
    return column(padding=32, gap=10)[
        virtual_list(len(rows), lambda i: service_row(rows[i]), item_height=64, gap=10, key="services"),
    ]
```

## 7. Filtros y valores derivados

Los valores derivados (totales, porcentajes, listas filtradas) **no se guardan**: se calculan
dentro de la vista a partir de los `Signal`. Una sola fuente de verdad, cero sincronización manual.

Añade esto al programa del paso anterior:

```python live continue size=900x540
from aurora import row, stat

show_down_only = Signal(False)


def summary():
    ss = services()
    up = [s for s in ss if s.online]
    avg = sum(s.latency_ms for s in up) / len(up) if up else 0
    return row(gap=16)[
        stat("EN LÍNEA", f"{len(up)}/{len(ss)}"),
        stat("LATENCIA MEDIA", f"{avg:.0f} ms"),
        stat("CAÍDOS", str(len(ss) - len(up)), positive=False),
    ]


def filter_chip():
    on = show_down_only()
    return row(
        padding=(6, 12),
        radius="$full",
        border_width=1,
        bg="$primary" if on else "$surface",
        border_color="$primary" if on else "$border",
        on_click=lambda: show_down_only.set(not on),
    )[text("Solo caídos", size=12, weight=600, color="#FFFFFF" if on else "$text")]


def view():
    visible = [s for s in services() if not show_down_only() or not s.online]
    return column(padding=32, gap=16)[
        summary(),
        row()[filter_chip()],
        [service_row(s) for s in visible],
        not visible and text("Todo funciona correctamente ✓", color="$success"),
    ]
```

`not visible and text(...)` es un patrón habitual: si la condición es falsa, el valor es `False`
y Aurora lo ignora.

### Imágenes

`image` acepta rutas o `bytes`, y SVG para iconos nítidos a cualquier tamaño. Fija un lado y el
otro se calcula solo; con los dos, `fit="cover"` llena la caja sin deformar:

```python
from aurora import image

row(gap=12, align="center")[
    image("avatar.jpg", width=40, height=40, fit="cover", radius="$full"),
    image("icons/check.svg", width=16),
]
```

### Dibujo libre con `canvas`

Para gráficos e indicadores que no son cajas, `canvas` te da un lienzo con comandos de dibujo.
Tu función recibe el lienzo ya con su tamaño, y se vuelve a llamar cuando cambia el estado:

```python live continue align=stretch
ventas = Signal([12, 18, 9, 22, 30, 26, 34, 28])  # oculto
from aurora import Canvas, canvas


def barras(c: Canvas):
    ancho = c.width / len(ventas())
    for i, v in enumerate(ventas()):
        alto = v / max(ventas()) * c.height
        c.rect(i * ancho + 2, c.height - alto, ancho - 4, alto, radius=4, fill="$primary")


canvas(barras, height=160)
```

Mira [`examples/canvas.py`](../examples/canvas.py) y la [referencia](reference.md) para el resto
de figuras (líneas, arcos, trazados, texto) y transformaciones.

### Gráficos con `chart`

Para series de datos no hace falta dibujar a mano: `chart` pinta el gráfico completo (ejes,
rejilla y leyenda) a partir de un array de numpy, una serie de polars o una lista.

```python
from aurora import chart

chart(cierres(), height=180)  # una línea
chart(df, names=["p50", "p95"], kind="area")  # varias series de un DataFrame
chart(visitas, labels=DIAS, kind="bar", height=140)  # barras por categoría
chart(ys, x=xs, kind="scatter", point_size=3)  # dispersión
chart(muestras, zoom=True)  # un millón de puntos, con rueda y arrastre
```

Con `kind` eliges la forma (`"line"`, `"area"`, `"bar"` o `"scatter"`); con una lista de series o
un DataFrame, varias series y su leyenda. Los datos **no se copian**: el gráfico lee la memoria
del array, así que si lo mutas en sitio basta con reconstruir la vista (por ejemplo, al cambiar
un `Signal`) para que se actualice. Las series largas se reducen con LTTB al dibujarlas, así que
un gráfico de millones de puntos se mueve sin problema; con `zoom=True` la rueda acerca (sobre el
puntero), el arrastre desplaza, la rueda horizontal también y el doble clic vuelve a la vista
completa, ajustando el eje y a lo que se ve.

Mira [`examples/charts.py`](../examples/charts.py) para un panel con las cuatro formas y la señal
con zoom.

### Más componentes

Además de `button`, `card`, `badge` y `stat`, Aurora trae `checkbox`, `switch`, `select`, `tabs`,
`avatar`, `divider`, `tooltip`, `progress`, `radio`, `segmented`, `slider`, `spinner`, `skeleton` y
`field` (etiqueta + control + error), y los de superposición: `dialog`, `toast`, `menu` y
`accordion`, más `pages` (una vista por página con transición). Los controles se enlazan a un
`Signal` igual que los campos de texto:

```python live continue
from aurora import checkbox, select, switch, tabs

notify = Signal(True)
region = Signal("eu")
view_mode = Signal("lista")

column(gap=14)[
    tabs([("lista", "Lista"), ("mapa", "Mapa")], view_mode, key="mode"),
    switch(notify, "Avisarme si un servicio cae"),
    select(region, [("eu", "Europa"), ("us", "EE. UU.")], key="region", width=200),
]
```

### Formularios

`text_input` y `textarea` se enlazan directamente a un `Signal[str]`: no hace falta escribir
manejadores para que el valor llegue a tu estado.

```python live continue size=480
from aurora import button, card  # oculto
from aurora import text_input, textarea

title = Signal("")
notes = Signal("")


def save(_text=None):
    add_note(title(), notes())
    title.set("")  # el campo se vacía solo
    notes.set("")


def form():
    return card(gap=10)[
        text_input(title, placeholder="Título", on_submit=save),
        textarea(notes, placeholder="Notas (Ctrl+Enter para guardar)", on_submit=save),
        button("Guardar", save, key="save"),
    ]


title.set("Migración de la base de datos")  # oculto
form()  # oculto
```

En los tests, `pilot.click("…")` enfoca un campo y `pilot.type("hola\n")` escribe en él.

## 8. Superposiciones: modales y toasts

Para dibujar algo **encima** del resto, usa `position="absolute"` con desplazamientos. Un modal
es un fondo semitransparente que cubre todo y, dentro, una tarjeta centrada:

```python live continue size=900x480
from aurora import box, button, card, row, text

selected = Signal(None)  # nombre del servicio abierto, o None


def detail_modal():
    name = selected()
    if name is None:
        return None
    s = next(s for s in services() if s.name == name)
    return box(
        position="absolute",
        top=0,
        right=0,
        bottom=0,
        left=0,
        bg="#000000AA",
        align="center",
        justify="center",
        on_click=lambda: selected.set(None),  # clic fuera: cerrar
    )[
        card(width=420, capture=True)[  # capture: los clics dentro no cierran
            text(s.name, size=20, weight=700),
            text(f"Región {s.region} · {s.latency_ms} ms", color="$muted"),
            row(gap=8, justify="end")[
                button("Cerrar", lambda: selected.set(None), variant="soft"),
                button("Reiniciar servicio", lambda: (toggle(s.name), selected.set(None))),
            ],
        ]
    ]


# oculto: inicio
def view():
    return box()[
        column(padding=32, gap=10)[[service_row(s) for s in services()]],
        detail_modal(),
    ]


selected.set("CDN")
# oculto: fin
```

Coloca el modal como **último hijo de la raíz** para que se pinte por encima de todo (o dale
`layer="overlay"`, que lo pinta encima aunque esté en otro sitio del árbol), y abre el
detalle desde la fila cambiando su `on_click` a `lambda: selected.set(s.name)`:

```python
def view():
    return box()[
        column(padding=32, gap=16)[...],  # tu contenido
        detail_modal(),
    ]
```

`capture=True` es la clave: sin él, un clic dentro de la tarjeta "subiría" hasta el fondo y
cerraría el modal.

¿No quieres montarlo a mano? `dialog` hace exactamente esto — fondo, tarjeta centrada, `capture`,
cierre al hacer clic fuera o con Esc y la animación de entrada y salida:

```python
dialog(selected() is not None, detalle(...), on_close=lambda: selected.set(None), width=420)
```

Y `toast(mensaje)` es el aviso flotante de abajo a la derecha, con punto de acento y un clic para
descartarlo. Todo esto está en la [referencia de componentes](reference.md#componentes).

### Teclado y atajos

Todo lo que tiene `on_click` ya se puede usar con el teclado: Tab mueve el foco (con un anillo
visible), Enter o Espacio lo activan. Para atajos, pon `on_key` en la raíz y devuelve `True` cuando
atiendas una tecla:

```python
def on_key(e):
    if e.matches("escape") and selected() is not None:
        selected.set(None)  # Esc cierra el modal
        return True
    return None


def view():
    return box(on_key=on_key)[...]
```

Dale `autofocus=True` al botón principal del modal para que el foco salte a él al abrirlo; mientras
esté abierto, Tab no sale de la tarjeta con `capture=True`.

### Animaciones

Hasta ahora el modal aparece y desaparece de golpe. Las animaciones en Aurora se **declaran**: dices
cómo entra y cómo sale un elemento, y el núcleo lo interpola en cada frame sin volver a llamar a
Python:

```python
from aurora import animate

card(width=420, capture=True, enter=animate.zoom(0.95), exit=animate.fade())[...]
```

Lo mismo sirve para la lista de servicios: con `animate_layout=True` cada fila se desliza a su
nuevo sitio cuando el filtro quita o añade otras, y con `transition` los cambios de color (el
estado de un servicio que se reinicia) se funden en vez de saltar:

```python
row(
    key=s.name,  # identidad estable: las animaciones siguen a cada fila por su key
    bg="$surface" if s.healthy else "#3A1E24",
    transition=animate.spring(),
    animate_layout=True,
    enter=animate.slide(y=8),
    exit=animate.fade(),
)[...]
```

`animate.spring()` es un muelle físico (natural y sin duración fija); `animate.tween(0.2)` es una
transición clásica de duración fija. Todo lo demás está en la
[referencia](reference.md#animaciones).

Los componentes ya vienen animados por defecto con esa misma escala: el knob de un switch se
desliza, la marca de un `checkbox` entra encogiéndose, el menú de un `select` aparece
deslizándose… Si prefieres que nada se mueva, `App(view, motion=False)` (o `AURORA_MOTION=0`).

## 9. Tema claro y oscuro

Pasa un `Signal[Theme]` a `App` y cámbialo cuando quieras. Como todo usa tokens, la interfaz
completa se actualiza:

```python live continue size=900x480
from aurora import DAYLIGHT, MIDNIGHT

theme = Signal(MIDNIGHT)


def toggle_theme():
    theme.set(DAYLIGHT if theme() is MIDNIGHT else MIDNIGHT)


App(view, title="Monitor", size=(900, 600), theme=theme).run()
selected.set(None)  # oculto
toggle_theme()  # oculto
```

Para crear tu propio tema, consulta [Temas y tokens](reference.md#temas-y-tokens).

## 10. Tests sin pantalla

`render_png` dibuja la vista exactamente como en la ventana, pero a un archivo. Sirve para tests
de snapshot, para CI sin pantalla y para generar capturas de documentación:

```python
def test_monitor_renders(tmp_path):
    app = App(view, size=(900, 600))
    app.render_png(str(tmp_path / "monitor.png"))
    assert (tmp_path / "monitor.png").stat().st_size > 0
```

Como la vista es una función de tus `Signal`, puedes preparar cualquier estado (un servicio caído,
el modal abierto, el tema claro) y renderizarlo sin simular ningún clic.

Para probar la **interacción**, `app.pilot()` ejecuta la app sin ventana y simula el puntero, con
el mismo hit-testing que la ventana real:

```python
def test_modal_opens_and_closes():
    pilot = App(view, size=(900, 600)).pilot()
    pilot.click("svc-CDN")  # clic en la fila con key="svc-CDN"
    assert selected() == "CDN"
    pilot.click_at(10, 10)  # clic en el fondo: cierra el modal
    assert selected() is None
```

Mientras desarrollas, el **inspector** enseña qué está pintando Aurora y cuánto cuesta.
Arranca la app con `AURORA_INSPECTOR=1` (o `App(view, inspector=True)`) y pulsa F12: verás el
árbol de la vista, el estilo y la caja de cada nodo y el coste de cada frame por fases. Con
Ctrl+Mayús+C eliges un nodo señalándolo en la interfaz. Los detalles están en la
[referencia](reference.md#inspector-y-profiler-de-frames).

Para iterar sobre el diseño sin reiniciar, arranca la app con **hot reload**:

```bash
aurora dev monitor.py
```

Cada vez que guardes, la ventana se actualiza con el código nuevo y conserva el estado: si tenías
un servicio seleccionado y el modal abierto, siguen así. Si algo falla, verás el error en la
ventana; corrígelo, guarda y sigue. Los detalles están en la
[referencia](reference.md#hot-reload).

## 11. Distribuir la app

Para que otros usen el monitor sin instalar Python, empaquétalo en un ejecutable. Primero instala
el empaquetador (una dependencia opcional) y luego un solo comando:

```bash
pip install "aurora-ui[build]"
aurora build monitor.py --name Monitor
```

Con uv: `uv add --dev "aurora-ui[build]"` y `uv run aurora build monitor.py --name Monitor`.

El resultado queda en `dist/` (`Monitor.exe` en Windows, `Monitor.app` en macOS): un único archivo
que puedes copiar a otro equipo con el mismo sistema.

Si la app usa imágenes u otros archivos, inclúyelos y ábrelos con `resource()`, que los encuentra
tanto al ejecutar con Python como dentro del ejecutable:

```python
from aurora import image, resource

image(resource("assets/logo.svg"), width=28)
```

```toml
# pyproject.toml: así basta con `aurora build`
[tool.aurora.build]
script = "monitor.py"
name = "Monitor"
icon = "assets/icon.ico"
include = ["assets"]
```

Mientras pruebas el ejecutable, `--console` mantiene la consola para ver los errores. Todas las
opciones están en la [referencia](reference.md#empaquetado-aurora-build).

---

## Siguientes pasos

- Lee el código de [`examples/studio.py`](../examples/studio.py): una app completa con
  navegación, kanban, gráficos y overlays que usa todo lo de esta guía.
- Revisa la [referencia](reference.md) para descubrir todas las propiedades de estilo.
- Si te interesa cómo funciona por dentro, sigue con la [arquitectura](architecture.md).
