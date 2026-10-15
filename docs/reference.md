# Referencia

Referencia completa de la API pública de Aurora. Para un recorrido paso a paso, empieza por la
[guía](guide.md).

- [App](#app)
- [Signal](#signal)
- [Pilot (tests de interacción)](#pilot-tests-de-interacción)
- [Primitivas](#primitivas)
- [Teclado y foco](#teclado-y-foco)
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
| `wheel(dy=0, dx=0, *, lines=False)` | Rueda bajo el puntero; positivo = hacia el final del contenido. En píxeles (trackpad, inmediato) o, con `lines=True`, en pasos de rueda (animado). |
| `scroll(key, dy=0, dx=0)` | Mueve el puntero al centro de `key` y desplaza esos píxeles. |
| `scroll_offset(key)` | `(x, y)` desplazados del `scroll` con esa key, o `None`. |
| `press(combo)` | Pulsa y suelta una tecla o combinación: `"tab"`, `"shift+tab"`, `"enter"`, `"ctrl+s"`, `"a"`. |
| `key_down(combo)` / `key_up(combo)` | Pulsa / suelta por separado (p. ej. mantener Espacio). |
| `type(texto)` | Escribe en el campo enfocado, grafema a grafema, como desde el teclado (`"\n"` = Enter). |
| `ime_preedit(texto)` / `ime_commit(texto)` | Simulan la composición y la confirmación de un IME. |
| `selection(key)` | Selección del campo `key` en caracteres: `(inicio, fin)`, iguales si solo hay cursor. |
| `clipboard` | Portapapeles del piloto, en memoria (se puede leer y asignar); no toca el del sistema. |
| `focus(key)` | Enfoca `key` como si se llegara con el teclado. `LookupError` si no se pintó o no es enfocable. |
| `focused` | Key del nodo enfocado, o `None`. |
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
| `scroll(*, axis="y", **estilo)` | Contenedor desplazable (rueda, trackpad y barra arrastrable). Ver abajo. |
| `image(src, *, fit="contain", **estilo)` | Imagen de un archivo o de bytes. Ver abajo. |

### `image(src, *, fit="contain", **estilo)`

Muestra una imagen **PNG, JPEG, WebP, GIF** (primer fotograma), **BMP, ICO o SVG**. `src` es una
ruta (`str` o `Path`) o `bytes` con el archivo ya en memoria (p. ej. una gráfica generada con
matplotlib).

```python
image("assets/logo.svg", width=32)
image(cover_path, height=160, fit="cover", radius="$lg")
image(png_bytes)
```

- **Tamaño:** sin `width` ni `height`, ocupa su tamaño natural (1 píxel de la imagen = 1 píxel
  lógico) sin pasar del ancho disponible, como `max-width: 100%` en CSS. Con uno de los dos, el
  otro sale de su proporción. Sin `width`, no se estira en el eje cruzado de su contenedor.
- **`fit`** decide cómo encaja cuando fijas los dos lados: `"contain"` (entera, sin deformar,
  con márgenes si hace falta), `"cover"` (llena la caja recortando lo que sobra), `"fill"`
  (estirada) o `"none"` (tamaño natural, centrada y recortada).
- Se recorta a las esquinas del elemento: con `radius="$full"` y `fit="cover"` tienes un avatar.
- Los SVG se pintan como vectores: se ven nítidos a cualquier tamaño y densidad de pantalla. Su
  tamaño natural sale de `width`/`height` o, si no los tienen, del `viewBox`.
- Cada imagen se decodifica **una vez** y se reutiliza entre reconstrucciones. Si el archivo
  cambia en disco, se vuelve a leer en la siguiente reconstrucción.
- Un archivo que no existe lanza `FileNotFoundError`, y uno que no se puede decodificar,
  `ValueError`, ambos con la ruta en el mensaje.

### `scroll(*, axis="y", **estilo)`

Recorta su contenido a su caja (respetando `radius` y `border_width`) y lo desplaza en el eje
`axis`: `"y"` (vertical), `"x"` (horizontal) o `"both"`.

- Apila sus hijos en el eje que se desplaza (`direction="row"` con `axis="x"`) y **no los encoge**
  para que quepan: lo que sobra se desplaza. El `padding` forma parte del contenido desplazable.
- Uno vertical sin `height` ni `max_height` ocupa el espacio libre (`grow=1`). Con `height` o
  `max_height` tiene ese tamaño.
- La rueda del ratón se desplaza con suavizado; el trackpad, píxel a píxel (en macOS, con la inercia
  del sistema). Al llegar al límite, el desplazamiento pasa al `scroll` que lo contiene. Una rueda
  vertical también desplaza un `scroll` solo horizontal.
- La barra se superpone al contenido sin ocupar espacio. Aparece al desplazarse o al acercar el
  puntero al borde, y se oculta sola. Se puede arrastrar; pulsar fuera del pulgar lo lleva al puntero.
- Los hijos que quedan fuera de la zona visible no reciben clics ni hover.
- Dale una `key` para conservar la posición si el `scroll` cambia de sitio en el árbol. Si el
  contenido se encoge, la posición se ajusta sola.

```python
scroll(key="log", max_height=240, gap=6)[[text(line) for line in lines()]]
scroll(axis="x", gap=12)[[card(width=200)[...] for item in items()]]
```

Además de las propiedades de estilo, todos los elementos aceptan:

| Argumento | Descripción |
|---|---|
| `on_click` | Callable sin argumentos. Hace al elemento interactivo: cursor de mano, estados hover/pressed y clics. |
| `on_key` | Callable que recibe un [`KeyEvent`](#keyevent). Recibe las teclas cuando el foco está en el elemento o en uno de sus descendientes (la raíz las recibe siempre). Devuelve `True` para darla por atendida. |
| `on_focus` / `on_blur` | Callables sin argumentos: el elemento gana / pierde el foco. |
| `on_<evento>` | Todo argumento que empiece por `on_` se trata como manejador, no como estilo. |
| `focusable` | `bool`. Si el elemento recibe el foco con Tab y con clic. Por defecto, los que tienen `on_click`. |
| `autofocus` | `bool`. Toma el foco al aparecer en la vista (p. ej. el primer botón de un diálogo). Solo al aparecer: no lo roba en cada reconstrucción. |
| `key` | Identidad estable. Conserva el estado de animación aunque el elemento cambie de posición en el árbol. Recomendado en listas dinámicas. |

## Teclado y foco

Un elemento enfocado recibe el teclado. Se enfoca **con Tab / Shift+Tab** (en orden de pintura,
volviendo al principio al final) o **con un clic**; un clic en una zona sin elementos enfocables
quita el foco. Al llegar con el teclado se dibuja un **anillo de foco** animado, del color
heredable `focus_color` (`$primary` por defecto); con un clic no, como `:focus-visible` en CSS.
Si el elemento está dentro de un `scroll`, este se desplaza para mostrarlo.

Cada tecla pasa primero por los `on_key`, desde el elemento enfocado hacia la raíz (sin foco, solo
la raíz). El primero que devuelva un valor verdadero la da por atendida. Si nadie la atiende, se
aplica el comportamiento por defecto:

| Tecla | Por defecto |
|---|---|
| Tab / Shift+Tab | Foco al siguiente / anterior. Dentro de una barrera `capture=True` (un modal), el foco no sale de ella. |
| Enter | Activa (`on_click`) el elemento enfocado. |
| Espacio | Activa el elemento enfocado al soltarla, con la animación de pulsado. Sin elemento activable, avanza una página. |
| ↑ ↓ ← → | Desplazan el `scroll` que contiene al foco o, sin foco, el que está bajo el puntero. |
| RePág / AvPág, Inicio / Fin | Desplazan una página / hasta el principio o el final. |

Para atajos globales, pon `on_key` en la raíz de la vista:

```python
def on_key(e: KeyEvent):
    if e.matches("mod+n"):  # Ctrl+N (Cmd+N en macOS)
        add_task()
        return True
    if e.matches("escape"):
        modal.set(None)
        return True
    return None  # el resto, comportamiento normal


def view():
    return column(on_key=on_key)[...]
```

### `KeyEvent`

| Atributo | Descripción |
|---|---|
| `key` | Nombre de la tecla: `"Enter"`, `"Tab"`, `"Escape"`, `"Space"`, `"Backspace"`, `"Delete"`, `"ArrowUp"`, `"Home"`, `"PageDown"`, `"F1"`… o el carácter (`"a"`, `"A"`, `"?"`). |
| `text` | Texto que produce la tecla (`"a"`, `" "`), o `None` (teclas de control, atajos con Ctrl/Alt/Cmd). |
| `ctrl`, `shift`, `alt`, `meta` | Modificadores pulsados. `meta` es Cmd en macOS y la tecla Windows en Windows. |
| `repeat` | `True` si es una repetición por mantener la tecla. |
| `matches(combo)` | `True` si la pulsación es exactamente esa combinación: `"ctrl+s"`, `"shift+tab"`, `"escape"`, `"mod+k"` (`mod` = Cmd en macOS, Ctrl en el resto). Las letras no distinguen mayúsculas, y en los símbolos que requieren Shift (`"?"`) no hace falta escribirlo. Una combinación mal escrita lanza `ValueError`. |

Alias aceptados en las combinaciones: `esc`, `return`, `del`, `up`/`down`/`left`/`right`, `pgup`/`pgdn`,
`plus`; y como modificadores `control`, `option`, `cmd`, `super` y `win`.

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

### `text_input(value, *, placeholder="", on_change=None, on_submit=None, key=None, **estilo)`

Campo de texto de una línea. `value` es normalmente un `Signal[str]`, y entonces queda **enlazado
en los dos sentidos**: lo que se escribe actualiza el Signal y lo que asignes al Signal aparece en
el campo (por ejemplo, vaciarlo al enviar).

```python
query = Signal("")
text_input(query, placeholder="Buscar…", on_submit=lambda q: search(q))
```

| Parámetro | Descripción |
|---|---|
| `value` | `Signal[str]` (enlazado), o un `str`/callable con `on_change` para gestionar el valor tú. Sin `on_change`, un valor fijo no cambia al escribir. |
| `placeholder` | Texto atenuado que se muestra con el campo vacío. Se toma literalmente (un `"$"` inicial no es un token). |
| `on_change` | `fn(texto)` en cada cambio (después de actualizar el Signal). |
| `on_submit` | `fn(texto)` al pulsar Enter. |

Por defecto: `bg="$surface"`, borde de 1 px `$border`, `radius="$md"`, `padding=(9, 12)` y
200 px de ancho si su contenedor no le da otro (con `align="stretch"`, ocupa el ancho disponible).
Un campo con foco siempre muestra el anillo de foco, también tras un clic.

**Edición:** escribir (incluido texto compuesto con IME), Retroceso/Supr (con Ctrl, o Alt en macOS,
por palabras), flechas (con Mayús seleccionan; con Ctrl/Alt saltan palabras), Inicio/Fin,
Ctrl+A, Ctrl+C/X/V, Ctrl+Z y Ctrl+Mayús+Z o Ctrl+Y (Cmd en macOS). Con el ratón: clic coloca el
cursor (Mayús+clic amplía la selección), arrastrar selecciona, doble clic selecciona una palabra y
triple clic todo. El texto se recorre por grafemas: un emoji compuesto o una letra con tilde
combinada se borran de una vez. Tab sale del campo; las teclas pasan antes por los `on_key`.

### `textarea(value, *, placeholder="", rows=3, on_change=None, on_submit=None, key=None, **estilo)`

Como `text_input`, pero multilínea: Enter inserta un salto de línea y **Ctrl+Enter** (Cmd+Enter en
macOS) llama a `on_submit`. Las líneas largas se parten solas, y el campo **crece con el contenido**
a partir de un mínimo de `rows` líneas. Las flechas ↑ ↓ cambian de línea e Inicio/Fin van al
principio y al final de la línea. Para limitar su altura, ponlo dentro de un
`scroll(max_height=...)`: el cursor siempre se mantiene a la vista.

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
| `min_height`, `max_height` | número | — | Límites de alto. `max_height` en un `scroll` limita cuánto crece antes de desplazarse. |
| `grow` | número | `0` | Cuánto crece para ocupar espacio libre. |
| `shrink` | número | `1` | Cuánto se encoge si falta espacio. |
| `wrap` | `bool` | `False` | Permite saltar de línea a los hijos (rejillas de tarjetas). |
| `position` | `"absolute"` | relativo | Saca al elemento del flujo; se coloca con `top/right/bottom/left` respecto a su padre. Útil para modales, toasts y superposiciones. |
| `top`, `right`, `bottom`, `left` | número | — | Desplazamientos para `position="absolute"`. |
| `src` | ruta o `bytes` | — | Origen de una imagen. Usa la primitiva `image()`. |
| `fit` | `"contain"`, `"cover"`, `"fill"`, `"none"` | `"contain"` | Encaje de una imagen en su caja. |
| `scroll` | `"x"`, `"y"`, `"both"` | — | Convierte la caja en contenedor desplazable. Usa la primitiva `scroll()`, que añade buenos valores por defecto. |

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
| `scrollbar_color` | color | Color del pulgar de la barra de un `scroll` (se pinta translúcido). `scroll()` usa `$muted`. |
| `placeholder_color` | color | Color del placeholder de un campo de texto. Por defecto, el color del texto al 45 %. |
| `selection_color` | color | Fondo del texto seleccionado. Por defecto, `focus_color` translúcido. |
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
| `focus_color` | — | color del anillo de foco | `$primary` | *H* |
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
