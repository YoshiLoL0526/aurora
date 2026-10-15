# Referencia

Referencia completa de la API pública de Aurora. Para un recorrido paso a paso, empieza por la
[guía](guide.md).

- [App](#app)
- [Signal](#signal)
- [Pilot (tests de interacción)](#pilot-tests-de-interacción)
- [Primitivas](#primitivas)
- [Componentes](#componentes)
- [Propiedades de estilo](#propiedades-de-estilo)
- [Temas y tokens](#temas-y-tokens)
- [Formatos de valores](#formatos-de-valores)

---

## App

```python
App(view, *, title="Aurora", size=(960, 640), theme=MIDNIGHT)
```

| Parámetro | Tipo | Descripción |
|---|---|---|
| `view` | `Callable[[], Element]` | Función sin argumentos que devuelve el árbol de la interfaz. Se llama de nuevo tras cada evento. |
| `title` | `str` | Título de la ventana. |
| `size` | `tuple[float, float]` | Tamaño inicial en píxeles lógicos (independientes del DPI). |
| `theme` | `Theme \| Callable[[], Theme]` | Tema fijo, o un `Signal[Theme]` para cambiarlo en caliente. |

| Método | Descripción |
|---|---|
| `run()` | Abre la ventana y bloquea hasta que se cierra. |
| `render_png(path, *, size=None, scale=2.0)` | Renderiza la vista a PNG sin abrir ventana. `scale` es la densidad de píxeles (2.0 ≈ pantalla Retina). |
| `pilot(*, size=None, scale=1.0)` | Ejecuta la app sin ventana y devuelve un [`Pilot`](#pilot-tests-de-interacción) para simular interacción en tests. |
| `spawn(coro)` | Ejecuta una corrutina en un bucle `asyncio` en segundo plano (un hilo propio, creado la primera vez). Devuelve un `concurrent.futures.Future` con su resultado. |

El elemento raíz siempre ocupa la ventana completa. Si no defines `bg`, `color` o `font_family`
en la raíz, se toman del tema (`$background`, `$text` y la fuente del tema).

## Signal

```python
count = Signal(0)
```

| API | Descripción |
|---|---|
| `count()` / `count.value` | Lee el valor actual. |
| `count.set(v)` | Asigna un valor. Si es igual al actual (`==`), no hace nada. |
| `count.update(fn)` | Atajo para `count.set(fn(count()))`. |
| `count.subscribe(fn)` | Llama a `fn(valor)` en cada cambio. Devuelve una función para cancelar la suscripción. |

La interfaz se reconstruye tras cada evento de usuario y tras cada `set` que cambie un valor.
`set` es seguro desde **cualquier hilo o corrutina**: despierta el bucle de eventos, así que un
`Signal` actualizado por un hilo de trabajo o por una tarea de `app.spawn()` se ve en pantalla sin
esperar a que el usuario mueva el ratón.

```python
status = Signal("cargando…")


async def load():
    data = await fetch_data()
    status.set(f"{len(data)} filas")


app = App(view)
app.spawn(load())
app.run()
```

## Pilot (tests de interacción)

`app.pilot()` ejecuta la app **sin ventana** con el mismo runtime que la ventana real
(hit-testing, burbujeo, capas, reconstrucción) y simula el puntero frame a frame. Las coordenadas
están en píxeles lógicos y cada acción avanza un frame.

```python
def test_counter():
    pilot = App(view, size=(400, 300)).pilot()
    pilot.click("add")
    assert count() == 1
```

| API | Descripción |
|---|---|
| `click(key)` | Clic en el centro del nodo `key`, como una persona: si otro nodo lo tapa, el clic llega a ese otro. `LookupError` si el nodo no se pintó. |
| `click_at(x, y)` | Mueve el puntero, pulsa y suelta. |
| `move_to(x, y)` / `leave()` | Mueve el puntero / lo saca de la ventana. |
| `mouse_down()` / `mouse_up()` | Pulsa / suelta el botón izquierdo por separado. |
| `hovered` | Key del nodo interactivo bajo el puntero, o `None`. |
| `rect(key)` | `(x, y, ancho, alto)` del nodo en el último frame, o `None`. |
| `frame(dt=1/60)` | Avanza un frame. Devuelve `True` si quedan transiciones en curso. |
| `settle()` | Avanza frames hasta que terminen todas las transiciones. |
| `resize(ancho, alto)` | Cambia el tamaño de la "ventana". |
| `png(path)` | Guarda el último frame como PNG. |

Las excepciones de la vista y de los manejadores **se propagan** al test (con ventana, se
imprimen y la app sigue viva).

## Primitivas

Todas devuelven un `Element`. Los hijos se añaden con corchetes:

```python
column(gap=8)[text("a"), text("b")]
```

Dentro de los corchetes se aceptan elementos, listas (se aplanan), strings (se convierten en
`text`) y `None`/`False` (se ignoran, para poder escribir `condición and elemento`).

| Primitiva | Descripción |
|---|---|
| `box(**estilo)` | Contenedor genérico. Apila sus hijos en **columna** por defecto. |
| `column(**estilo)` | Contenedor con `direction="column"`. |
| `row(**estilo)` | Contenedor con `direction="row"`. |
| `text(contenido, **estilo)` | Texto. `contenido` puede ser un `str` o un callable (`lambda: f"{x()}"`), que se evalúa en cada reconstrucción. |
| `spacer()` | Caja con `grow=1`: ocupa todo el espacio libre del eje principal. |

Además de las propiedades de estilo, todos los elementos aceptan:

| Argumento | Descripción |
|---|---|
| `on_click` | Callable sin argumentos. Hace al elemento interactivo: cursor de mano, estados hover/pressed y clics. |
| `on_<evento>` | Manejador de evento. Todo argumento que empiece por `on_` se trata como manejador, no como estilo. Por ahora el núcleo solo emite `click`; el resto llegará con teclado, foco e input de texto. |
| `key` | Identidad estable. Conserva el estado de animación aunque el elemento cambie de posición en el árbol. Recomendado en listas dinámicas. |

## Componentes

Construidos solo con primitivas: puedes leerlos en `python/aurora/components.py` y usarlos como
plantilla para los tuyos. Todos aceptan propiedades de estilo extra, que sobrescriben las suyas.

### `button(label, on_click=None, *, variant="primary", key=None, **estilo)`

| `variant` | Aspecto |
|---|---|
| `"primary"` | Color de marca con brillo; acción principal. |
| `"soft"` | Superficie con borde; acciones secundarias. |
| `"ghost"` | Transparente hasta el hover; acciones terciarias. |

Por defecto: `padding=(10, 18)`, `radius="$md"`, contenido centrado, `font_weight=600`,
`press_scale=0.96`.

### `card(**estilo)`

Columna con superficie, borde sutil, sombra y esquinas grandes. Por defecto: `bg="$surface"`,
`radius="$lg"`, `padding=20`, `gap=12`, `border_width=1`, `border_color="$border"`,
`shadow=(0, 10, 30, "$shadow")`.

### `badge(label, *, tone="accent")`

Píldora compacta de texto. `tone` es el nombre de un token de color del tema.

### `stat(label, value, delta=None, *, positive=True)`

Tarjeta de métrica: etiqueta, valor grande y variación opcional en verde (`positive=True`) o rojo.
Tiene `grow=1`, así que varias `stat` en una `row` se reparten el ancho.

## Propiedades de estilo

Las longitudes están en **píxeles lógicos**. Las propiedades marcadas con *H* se **heredan** de los
contenedores (como en CSS).

### Layout

| Propiedad | Valores | Por defecto | Descripción |
|---|---|---|---|
| `direction` | `"row"`, `"column"` | `"column"` | Eje principal. |
| `gap` | número | `0` | Espacio entre hijos. |
| `padding` | número · `(v, h)` · `(t, r, b, l)` | `0` | Relleno interior. |
| `align` | `"start"`, `"center"`, `"end"`, `"baseline"`, `"stretch"` | `"stretch"` | Alineación en el eje cruzado. `"baseline"` alinea textos de distinto tamaño por su línea base. |
| `justify` | `"start"`, `"center"`, `"end"`, `"between"`, `"around"`, `"evenly"` | `"start"` | Distribución en el eje principal. |
| `width`, `height` | número · `"50%"` | automático | Tamaño fijo o relativo al contenedor. |
| `min_width`, `max_width` | número | — | Límites de ancho. |
| `grow` | número | `0` | Cuánto crece para ocupar espacio libre. |
| `shrink` | número | `1` | Cuánto se encoge si falta espacio. |
| `wrap` | `bool` | `False` | Permite saltar de línea a los hijos (rejillas de tarjetas). |
| `position` | `"absolute"` | relativo | Saca al elemento del flujo; se coloca con `top/right/bottom/left` respecto a su padre. Útil para modales, toasts y superposiciones. |
| `top`, `right`, `bottom`, `left` | número | — | Desplazamientos para `position="absolute"`. |

> **Truco: columnas de igual ancho.** `grow=1, width=0` en cada hijo de una `row` reparte el
> espacio a partes iguales, sin importar su contenido.

### Apariencia

| Propiedad | Valores | Descripción |
|---|---|---|
| `bg` | color | Color de fondo. |
| `bg_hover` | color | Fondo con el cursor encima (requiere `on_click`). Transición animada. |
| `bg_pressed` | color | Fondo mientras se mantiene pulsado. Transición animada. |
| `gradient` | `(desde, hasta, ángulo)` | Gradiente lineal. Ángulo en grados: `0` = izquierda→derecha, `90` = arriba→abajo. Reemplaza a `bg`. |
| `radius` | número | Radio de las esquinas. Usa `999` (o `"$full"`) para píldoras y círculos. |
| `border_width` | número | Grosor del borde (también reserva espacio en el layout). |
| `border_color` | color | Color del borde. |
| `shadow` | `(dx, dy, blur, color)` | Sombra difuminada desplazada. |
| `opacity` | `0.0` – `1.0` | Opacidad del elemento y todos sus hijos. |
| `press_scale` | número | Escala al pulsar (p. ej. `0.96`). Animada. |
| `capture` | `bool` | Barrera de eventos: los clics dentro no llegan a los ancestros. Úsalo en el contenido de un modal. |
| `layer` | `"base"`, `"overlay"` | Con `"overlay"`, el elemento se maqueta en su sitio pero se pinta y recibe eventos **por encima de todo el árbol**, aunque se declare antes que otros. Ideal para desplegables, tooltips y modales. Se pinta en coordenadas absolutas: no hereda la `opacity` ni el `press_scale` de sus ancestros. Los clics siguen burbujeando por sus ancestros del árbol. |

### Texto

| Propiedad | Alias | Valores | Por defecto | |
|---|---|---|---|---|
| `font_size` | `size` | número | `14` | *H* |
| `font_weight` | `weight` | `100`–`900` | `400` | *H* |
| `color` | — | color | `$text` | *H* |
| `font_family` | `family` | nombre de fuente | fuente del tema (`Inter`) | *H* |
| `line_height` | — | múltiplo del tamaño (`1.4`) | el de la fuente | *H* |
| `letter_spacing` | — | número (px, admite negativos) | `0` | *H* |
| `max_lines` | — | entero | sin límite | Corta con `…` al superar ese número de líneas. |
| `text_align` | — | `"left"`, `"center"`, `"right"` | `"left"` | Alineación dentro del ancho del texto. |

Si la fuente pedida no está instalada, se usa la de reserva del sistema, y los glifos que falten
(emoji, símbolos) se buscan automáticamente en otras fuentes.

## Temas y tokens

En cualquier propiedad que acepte color o radio puedes usar un **token**: un string que empieza
por `$` y se resuelve con el tema activo.

```python
box(bg="$surface", radius="$lg", shadow=(0, 8, 24, "$shadow"))
```

### Tokens incluidos

| Colores | Uso |
|---|---|
| `$background` | Fondo de la ventana |
| `$surface`, `$surface_hover`, `$surface_pressed` | Tarjetas, paneles y sus estados |
| `$border` | Bordes sutiles |
| `$text`, `$muted` | Texto principal y secundario |
| `$primary`, `$primary_hover`, `$primary_pressed` | Color de marca y sus estados |
| `$accent`, `$success`, `$danger` | Acentos y semántica |
| `$shadow`, `$glow` | Sombras neutras y brillo de marca |

| Radios | |
|---|---|
| `$sm` `8` · `$md` `12` · `$lg` `18` · `$full` `999` | |

### Temas incluidos y temas propios

`MIDNIGHT` (oscuro, por defecto) y `DAYLIGHT` (claro) definen todos los tokens. Para crear el tuyo:

```python
from aurora import MIDNIGHT, Theme

OCEAN = Theme(
    colors={
        **MIDNIGHT.colors,
        "primary": "#0EA5E9",
        "primary_hover": "#38BDF8",
        "primary_pressed": "#0284C7",
        "glow": "#0EA5E940",
    },
    radius=MIDNIGHT.radius,
    font_family="Inter",
)
```

Un token que no existe en el tema lanza `KeyError` al construir la vista, para que los errores
de escritura se detecten enseguida.

## Formatos de valores

| Tipo | Formato |
|---|---|
| Color | `"#rgb"`, `"#rrggbb"` o `"#rrggbbaa"` (el último par es la opacidad: `"#00000080"` = negro al 50 %). También tokens `"$nombre"`. |
| Longitud | Número en píxeles lógicos, o `"NN%"` en `width`/`height`. |
| Ángulo | Grados (`float`). |

Un color mal escrito lanza `ValueError` con el valor problemático en el mensaje.
