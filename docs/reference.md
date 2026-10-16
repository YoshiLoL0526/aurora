# Referencia

Referencia completa de la API pública de Aurora. Para un recorrido paso a paso, empieza por la
[guía](guide.md).

- [App](#app)
- [Signal](#signal)
- [component](#component)
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
| `run(*, backend="auto")` | Abre la ventana y bloquea hasta que se cierra. `backend` elige dónde se pinta: `"gpu"` (Vulkan en Windows y Linux, Metal en macOS), `"cpu"` o `"auto"` (GPU si se puede iniciar; si no, CPU). Con `"auto"`, la variable de entorno `AURORA_BACKEND` (`gpu`/`cpu`) lo fuerza. `"gpu"` sin GPU disponible lanza `RuntimeError`; un valor desconocido, `ValueError`. |
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

La interfaz se reconstruye tras cada evento de usuario y tras cada `set` que cambie un valor;
los [`@component`](#component) que no dependan de lo que cambió se reutilizan.
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

## component

```python
@component
def fila(tarea: Tarea, seleccionada: bool):
    return row(key=f"tarea-{tarea.id}", bg="$surface" if seleccionada else None)[...]
```

`view()` se vuelve a llamar entera tras cada cambio, pero un `@component` **no se reconstruye** si
sus argumentos son iguales (`==`) a los de la última vez y no cambió ningún `Signal` que leyera, al
construirse o al resolver sus textos con lambda. Devuelve el mismo `Element`, que recuerda su
serialización, y el núcleo reutiliza el nodo ya procesado: el coste de esa rama en Python y en el
parseo desaparece. Es la forma de escalar listas grandes: en una de 10 000 filas, cambiar la
selección reconstruye 2 filas en vez de 10 000.

- Pasa como argumento lo que distingue a cada instancia (`seleccionada`) en vez de leer un
  `Signal` compartido dentro: un componente que lee `selected()` depende de él y se reconstruye
  cada vez que cambia.
- Los argumentos deben ser **hashables** (números, cadenas, tuplas, dataclasses congeladas). Con
  argumentos no hashables el componente funciona, pero no se memoriza.
- Depende solo de sus argumentos y de `Signal`. Si lee estado mutable normal (una lista global, un
  atributo de un objeto), no se entera de sus cambios.
- No pases lambdas creadas en cada llamada como argumento: son distintas cada vez. Créalas dentro
  del componente (`on_click=lambda: selected.set(tarea.id)`).
- Un componente puede contener otros: si cambia el de dentro, se reconstruye también el de fuera.
- Se olvidan las instancias que no aparecen en la última reconstrucción de la vista.

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
| `drag(key, dx=0, dy=0, steps=4)` | Pulsa en el centro de `key`, mueve el puntero `(dx, dy)` en `steps` pasos y suelta. |
| `cursor` | Cursor del ratón en el último frame: `"default"`, `"pointer"`, `"text"`, `"grab"`, `"grabbing"`, `"col-resize"` o `"row-resize"`. |
| `move_to(x, y)` / `leave()` | Mueve el puntero / lo saca de la ventana. |
| `mouse_down()` / `mouse_up()` | Pulsa / suelta el botón izquierdo por separado. |
| `wheel(dy=0, dx=0, *, lines=False)` | Rueda bajo el puntero; positivo = hacia el final del contenido. En píxeles (trackpad, inmediato) o, con `lines=True`, en pasos de rueda (animado). |
| `scroll(key, dy=0, dx=0)` | Mueve el puntero al centro de `key` y desplaza esos píxeles. |
| `scroll_offset(key)` | `(x, y)` desplazados del `scroll` con esa key, o `None`. |
| `chart_view(key)` | Ventana visible del eje x del `chart` con esa key, en unidades de datos (sin zoom, su dominio completo). |
| `press(combo)` | Pulsa y suelta una tecla o combinación: `"tab"`, `"shift+tab"`, `"enter"`, `"ctrl+s"`, `"a"`. |
| `key_down(combo)` / `key_up(combo)` | Pulsa / suelta por separado (p. ej. mantener Espacio). |
| `type(texto)` | Escribe en el campo enfocado, grafema a grafema, como desde el teclado (`"\n"` = Enter). |
| `ime_preedit(texto)` / `ime_commit(texto)` | Simulan la composición y la confirmación de un IME. |
| `selection(key)` | Selección del campo `key` en caracteres: `(inicio, fin)`, iguales si solo hay cursor. |
| `clipboard` | Portapapeles del piloto, en memoria (se puede leer y asignar); no toca el del sistema. |
| `focus(key)` | Enfoca `key` como si se llegara con el teclado. `LookupError` si no se pintó o no es enfocable. |
| `focused` | Key del nodo enfocado, o `None`. |
| `tooltip` | Texto del tooltip visible, o `None`. Avanza el tiempo con `frame(dt=0.6)` para que aparezca. |
| `hovered` | Key del nodo interactivo bajo el puntero, o `None`. |
| `rect(key)` | `(x, y, ancho, alto)` del nodo en el último frame, o `None`. |
| `frame(dt=1/60)` | Avanza un frame. Devuelve `True` si quedan transiciones en curso. |
| `settle()` | Avanza frames hasta que terminen todas las transiciones. |
| `resize(ancho, alto)` | Cambia el tamaño de la "ventana". |
| `png(path)` | Guarda el último frame como PNG. |
| `stats` | Coste del último frame por fases, en milisegundos: `build` (tu `view()` y la serialización), `parse`, `style` (comparar el árbol nuevo con el anterior), `layout`, `draw` (las funciones `draw` de los `canvas` y la grabación de los `chart`) y `paint` (composición y pintura); además `nodes` (nodos del árbol), `rebuilt` (si se reconstruyó la vista; si no, `build`, `parse` y `style` valen 0), `layout_cached` (si se reutilizó el layout del frame anterior) y `damage`, la zona repintada `(x, y, ancho, alto)` o `None` si el frame no pintó nada. Lo usa la [suite de benchmarks](../benchmarks/README.md). |

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
| `canvas(draw, **estilo)` | Lienzo de dibujo inmediato. Ver abajo. |
| `chart(y, *, kind="line", **estilo)` | Gráfico nativo (línea, área, barras, dispersión) alimentado por arrays. Ver abajo. |

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

### `canvas(draw, **estilo)`

Lienzo de **dibujo inmediato**: `draw(c)` recibe un `Canvas` del tamaño de la caja y dibuja en él
con comandos sueltos, como un `<canvas>` de HTML. Para gráficos, indicadores, diagramas o
cualquier cosa que no sea una composición de cajas.

```python
from aurora import Canvas, canvas


def sparkline(c: Canvas):
    step = c.width / (len(values) - 1)
    points = [(i * step, c.height - v * c.height) for i, v in enumerate(values)]
    c.polyline(points, stroke="$primary", stroke_width=2)
    c.text(c.width, 0, "máx.", align="right", size=11, color="$muted")


canvas(sparkline, height=60, bg="$surface", radius="$md", padding=8)
```

- **Coordenadas:** píxeles lógicos con el origen en la esquina superior izquierda de la caja de
  contenido (dentro del `padding`) y el eje y hacia abajo. `c.width` y `c.height` son su tamaño.
  Lo que se sale se recorta (también a las esquinas redondeadas).
- **Tamaño:** sin `height`, `grow`, `min_height` ni `max_height` mide 200 px de alto; a lo ancho
  se estira como cualquier caja. Admite el estilo de una caja (`bg`, `radius`, `border_*`,
  `shadow`…), manejadores (`on_click`…) e hijos con `[...]`, que se pintan encima del dibujo.
- **Cuándo se llama a `draw`:** después del layout (por eso ya conoce su tamaño), cada vez que
  la vista se reconstruye y cuando el lienzo cambia de tamaño. Hover, scroll y animaciones de
  otros nodos **no** lo llaman: el dibujo grabado se repinta sin volver a Python. Dentro de un
  `@component` que no se reconstruye, `draw` solo se repite si cambia el tamaño o algún `Signal`
  que lea la propia función.
- **En lote:** los comandos se acumulan en Python y cruzan al núcleo de una vez, donde se graban
  en un `Picture` de Skia. Las listas de puntos viajan como un bloque de `float32`; un array de
  numpy de forma `(n, 2)` se convierte sin recorrerlo en Python.
- Un comando inválido (color desconocido, `dash` impar…) lanza `ValueError`; una excepción en
  `draw` se propaga como las de la vista.

Métodos de `Canvas`. Los colores aceptan tokens (`"$primary"`) y hex con alfa. Las figuras se
rellenan con `fill`, se perfilan con `stroke` (de grosor `stroke_width`) o ambas cosas; sin
ninguno de los dos usan `$primary` (rellenas las figuras cerradas, trazadas las líneas y arcos).
`dash=(on, off, ...)` hace el trazo discontinuo.

| Método | Descripción |
|---|---|
| `clear(color="$background")` | Rellena todo el lienzo. |
| `rect(x, y, w, h, *, radius=0, fill, stroke, stroke_width=1, dash)` | Rectángulo, con esquinas redondeadas opcionales. |
| `oval(x, y, w, h, ...)` / `circle(cx, cy, r, ...)` | Elipse inscrita en el rectángulo / círculo. |
| `arc(cx, cy, r, start, sweep, *, pie=False, ..., cap="butt")` | Arco (grados, 0 = derecha, sentido horario). `pie=True` lo cierra por el centro. |
| `line(x1, y1, x2, y2, *, stroke="$primary", stroke_width=1, cap="butt", dash)` | Segmento. |
| `polyline(points, *, stroke, fill, stroke_width=1, closed=False, cap, join="round", dash)` | Línea quebrada por `[(x, y), ...]` o un array `(n, 2)`. |
| `polygon(points, *, fill, stroke, ...)` | Polígono cerrado y relleno. |
| `path(path, *, fill, stroke, ...)` | Trazado libre (`Path`, abajo). |
| `text(x, y, content, *, color="$text", size=14, weight=400, family=None, align="left", baseline="top")` | Una línea de texto. `align` (`"left"`, `"center"`, `"right"`) la coloca respecto a `x`; `baseline` (`"top"`, `"middle"`, `"alphabetic"`, `"bottom"`) respecto a `y`. La familia por defecto es la del tema. |
| `save()` / `restore()` / `saved()` | Guardan y recuperan la transformación y el recorte. `with c.saved(): ...` hace las dos cosas. |
| `translate(dx, dy)` / `scale(sx, sy=None)` / `rotate(grados)` | Transforman lo que se dibuje después. |
| `clip_rect(x, y, w, h)` | Recorta lo que se dibuje después (hasta el próximo `restore`). |

`cap`: `"butt"`, `"round"` o `"square"`; `join`: `"miter"`, `"round"` o `"bevel"`.

`Path()` construye trazados encadenando `move_to(x, y)`, `line_to(x, y)`,
`quad_to(cx, cy, x, y)`, `cubic_to(c1x, c1y, c2x, c2y, x, y)`, `arc(cx, cy, r, start, sweep)` y
`close()`:

```python
c.path(Path().move_to(0, 40).quad_to(30, 0, 60, 40).close(), fill="$accent")
```

### `chart(y, *, x=None, kind="line", **estilo)`

Gráfico nativo: **línea**, **área**, **barras** o **dispersión**, con los ejes, la rejilla y la
leyenda calculados solos. Los datos se leen de los arrays **sin copiarlos**.

```python
from aurora import chart

chart(ventas(), height=160)  # una línea
chart(df, names=["p50", "p95"], kind="area")  # varias series de un DataFrame
chart(cierres, labels=DIAS, kind="bar", height=140)
chart(ys, x=xs, kind="scatter", point_size=3)
chart(muestras, zoom=True)  # millones de puntos: rueda para acercar, arrastra para mover
```

- **Datos:** `y` puede ser un array de numpy, un `array.array`, un `memoryview` o una lista; una
  `Series` o un `DataFrame` de polars (o cualquier cosa con `to_numpy()`, como pandas — un
  DataFrame aporta **una serie por columna**); una **lista de series**; o un array 2-D `(n, m)`,
  una serie por columna. Los datos cruzan al núcleo **sin copiarse**: el gráfico lee la memoria
  del array, así que mutarlo en sitio y reconstruir la vista basta para actualizarlo (los de
  polars se convierten con `to_numpy()`, que comparte memoria cuando el tipo lo permite). Los
  valores que falten (`NaN`) se saltan y, en una línea o un área, la cortan.
- **Millones de puntos:** al grabar, cada serie se reduce en Rust con **LTTB**
  (*Largest-Triangle-Three-Buckets*) a ~2 puntos por píxel: el perfil y los picos se conservan y
  solo se recorren los puntos visibles (con x ordenada, por búsqueda binaria). Un gráfico de un
  millón de puntos se graba en milisegundos y se mueve a 60 fps.
- **Zoom y pan:** con `zoom=True`, la rueda acerca y aleja sobre el puntero (el dato bajo el
  cursor no se mueve), el arrastre desplaza la ventana, la rueda horizontal (trackpad) también
  desplaza y el doble clic vuelve a la vista completa. El eje y se ajusta a lo visible salvo que
  fijes `y_min`/`y_max`; al llegar a un tope, la rueda pasa al `scroll` de fuera. La ventana es
  estado del gráfico (su `key`) y sobrevive a las reconstrucciones; `Pilot.chart_view(key)` la
  lee en los tests.
- **Series:** `color` admite un color o una lista (uno por serie; sin él, rota la paleta del
  tema) y `names` dibuja la leyenda de arriba.
- **Ejes:** el de x son posiciones 0, 1, 2… salvo que des `x` (numérico) o `labels` (categorías:
  meses, días…). El de y sale de los datos, con ticks redondos, o de `y_min`/`y_max` (los dos
  juntos deben ser coherentes). Las barras siempre nacen del cero y, con varias series, se
  agrupan (una al lado de otra). `grid=False` quita la rejilla.
- **Aspecto:** `stroke_width` (grosor de la línea, 2), `point_size` (radio de la dispersión, 3.5),
  `bar_width` (fracción del hueco de cada barra, 0.7), `label_size`, `label_color` y `grid_color`;
  admite el estilo de una caja (`bg`, `radius`, `padding`, `border_*`…) y manejadores como
  `on_click` (que recibe el clic en el gráfico, no en cada barra).
- **Tamaño:** sin `height`, `grow`, `min_height` ni `max_height` mide 200 px de alto; a lo ancho
  se estira como cualquier caja (en una `row`, dale `grow=1` o `width`).
- **Cuándo se vuelve a grabar:** cuando la vista se reconstruye con otros datos u opciones, cuando
  cambia su caja o cuando la rueda o el arrastre mueven la ventana. Hover, scroll y animaciones de
  otros nodos lo repintan sin releer los datos. Dentro de un `@component`, solo si cambian sus
  argumentos o algún `Signal` que lea.
- Un dato no numérico (texto, complejos…), unas `labels` que no encajen con los puntos o una
  `kind` desconocida lanzan `ValueError` (`TypeError` si los datos no son ni números ni arrays).

Ejemplo completo en [`examples/charts.py`](../examples/charts.py).

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
- `on_scroll` recibe un `ScrollEvent` (`x`, `y`: desplazamiento; `width`, `height`: tamaño de la
  zona visible, en píxeles lógicos) en el primer frame y cada vez que alguno cambia. A diferencia
  de los demás manejadores no reconstruye la vista por sí solo (se llama en cada frame de
  desplazamiento): si cambias un `Signal` en él, la vista se reconstruye en ese mismo frame. Para
  listas muy largas, [`virtual_list`](#virtual_listcount-item--item_height-key-gap0-overscan4-estilo)
  ya lo usa por ti.

```python
scroll(key="log", max_height=240, gap=6)[[text(line) for line in lines()]]
scroll(axis="x", gap=12)[[card(width=200)[...] for item in items()]]
```

Además de las propiedades de estilo, todos los elementos aceptan:

| Argumento | Descripción |
|---|---|
| `on_scroll` | En un `scroll`: callable que recibe un `ScrollEvent` cuando cambian el desplazamiento o la zona visible. Ver [`scroll`](#scroll-axisy-estilo). |
| `on_click` | Callable sin argumentos. Hace al elemento interactivo: cursor de mano, estados hover/pressed y clics. |
| `on_drag` | Callable que recibe un [`DragEvent`](#dragevent). Pulsar sobre el elemento empieza un arrastre: le llegan todos los movimientos hasta soltar, aunque el puntero salga de su caja. Si el puntero llega a moverse, el gesto no cuenta como clic. Hace al elemento interactivo (hover/pressed) pero no enfocable. |
| `on_key` | Callable que recibe un [`KeyEvent`](#keyevent). Recibe las teclas cuando el foco está en el elemento o en uno de sus descendientes (la raíz las recibe siempre). Devuelve `True` para darla por atendida. |
| `on_focus` / `on_blur` | Callables sin argumentos: el elemento gana / pierde el foco. |
| `on_<evento>` | Todo argumento que empiece por `on_` se trata como manejador, no como estilo. |
| `focusable` | `bool`. Si el elemento recibe el foco con Tab y con clic. Por defecto, los que tienen `on_click`. |
| `autofocus` | `bool`. Toma el foco al aparecer en la vista (p. ej. el primer botón de un diálogo). Solo al aparecer: no lo roba en cada reconstrucción. |
| `key` | Identidad estable. Conserva el estado de animación aunque el elemento cambie de posición en el árbol. Recomendado en listas dinámicas. Un elemento sin `key` recibe la de su padre seguida de su posición (`"fila-7/0"`, `"fila-7/1"`…), así que los hijos siguen a su padre si este se mueve. |

### `DragEvent`

Lo que reciben los manejadores `on_drag`, en píxeles lógicos:

| Atributo | Descripción |
|---|---|
| `phase` | `"start"` al pulsar, `"move"` en cada movimiento y `"end"` al soltar. |
| `x`, `y` | Posición actual del puntero en la ventana. |
| `dx`, `dy` | Desplazamiento desde donde se pulsó (no desde el último evento). |

```python
ancho = Signal(240.0)
inicio = {}


def redimensionar(e: DragEvent):
    if e.phase == "start":
        inicio["ancho"] = ancho()
    ancho.set(max(120, inicio["ancho"] + e.dx))


row()[
    column(width=ancho())[...],
    box(width=6, cursor="col-resize", bg_hover="$border", on_drag=redimensionar),
]
```

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

### `divider(*, vertical=False, color="$border", **estilo)`

Línea de 1 px. Horizontal por defecto (ocupa el ancho de su columna); con `vertical=True`, para
separar elementos de una `row` (ocupa su alto, o el `height` que le des).

### `avatar(name="", *, src=None, size=32, **estilo)`

Círculo de `size` px. Con `src` (ruta o `bytes`) muestra la imagen recortada (`fit="cover"`); sin
ella, las iniciales de `name` (hasta dos) sobre un color del tema que depende del nombre, así que
una persona siempre tiene el mismo color.

```python
avatar("Ada Lovelace")
avatar("Ada Lovelace", src="ada.jpg", size=40, tooltip="Ada · Admin")
```

### `checkbox(checked, label=None, *, on_change=None, key=None, **estilo)` y `switch(on, label=None, ...)`

Casilla de verificación e interruptor. Con un `Signal[bool]` se enlazan solos: un clic (o Enter /
Espacio con el foco) lo alterna. `on_change(valor)` se llama en cada cambio; con un `bool` fijo y
`on_change`, gestionas el valor tú. Toda la fila (control y etiqueta) es la zona de clic.

```python
dark = Signal(True)
switch(dark, "Tema oscuro", on_change=lambda on: theme.set(MIDNIGHT if on else DAYLIGHT))
checkbox(accepted, "Acepto las condiciones")
```

### `tabs(options, selected, *, key=None, **estilo)`

Pestañas con indicador bajo la activa. `options` es una lista de valores o de pares
`(valor, etiqueta)` y `selected` el `Signal` con el valor activo. Con una pestaña enfocada, ← y →
cambian de pestaña. Cada pestaña tiene la key `f"{key}-{valor}"`.

```python
page = Signal("resumen")
tabs([("resumen", "Resumen"), ("tablero", "Tablero")], page, key="nav")
```

### `select(value, options, *, placeholder="Elegir…", key=None, **estilo)`

Desplegable. `value` es un `Signal` y `options`, valores o pares `(valor, etiqueta)`. La lista se
abre por encima de todo (`layer="overlay"`), con scroll si es larga, y se cierra al elegir, al hacer
clic fuera, con Esc o con Enter. Con el desplegable enfocado, ↑ y ↓ cambian el valor sin abrirlo.
Ancho mínimo de 160 px; los estilos extra (`width`, `grow`…) se aplican al contenedor. Las opciones
tienen la key `f"{key}-opt-{índice}"`.

```python
lang = Signal("es")
select(lang, [("es", "Español"), ("en", "English")], key="lang", width=220)
```

### `virtual_list(count, item, *, item_height, key, gap=0, overscan=4, **estilo)`

Lista desplazable de `count` filas que **solo construye las visibles**: con 100 000 filas, cada
reconstrucción crea unas pocas decenas y desplazarse cuesta lo mismo que con 20.

```python
@component
def fila(i: int, seleccionada: bool):
    return row(grow=1, padding=(0, 12), align="center", bg="$surface" if seleccionada else None)[
        text(tareas()[i].titulo)
    ]


virtual_list(len(tareas()), lambda i: fila(i, i == elegida()), item_height=36, key="tareas")
```

- `item(i)` devuelve la fila `i`. Cada fila ocupa un hueco de todo el ancho y `item_height` de alto
  (más `gap` entre filas): dale `grow=1` a su raíz para que lo rellene. Todas las filas miden lo
  mismo; así la lista conoce su alto total sin construirlas.
- Se comporta como un [`scroll`](#scroll-axisy-estilo) vertical (los `**estilo` van a él) y la
  `key`, obligatoria, guarda su posición y su zona visible.
- Al desplazarse solo se reconstruye cuando cambia el rango de filas visibles, en el mismo frame.
  `overscan` filas de más por cada lado cubren el desplazamiento entre medias.
- Con filas `@component`, las que siguen visibles no se reconstruyen.
- Solo las filas construidas existen en el árbol: Tab recorre las visibles, y `Pilot.rect` de una
  fila fuera de la zona visible devuelve `None`.

### `table(rows, columns, *, key, sort=None, widths=None, on_row_click=None, row_height=36, header_height=40, striped=True, empty="Sin datos", overscan=4, **estilo)`

Tabla de datos con cabecera fija, **ordenación**, **columnas redimensionables** y filas
**virtualizadas**: solo se construyen las visibles, así que con 100 000 filas desplazarse cuesta
lo mismo que con 20.

```python
from aurora import Column, table

table(
    pedidos(),
    [
        Column("id", "Nº", width=80, align="end"),
        Column("cliente", "Cliente", width=220),
        Column("total", "Total", align="end", format=lambda v: f"{v:,.2f} €"),
        Column("estado", "Estado", cell=lambda p: badge(p.estado), sortable=False),
    ],
    key="pedidos",
    on_row_click=lambda p: abierto.set(p.id),
)
```

- `rows` es cualquier secuencia: dicts, tuplas, dataclasses u otros objetos. `columns` son
  objetos `Column` o simplemente keys (`["id", "nombre"]`).
- **Ordenar:** pulsar una cabecera ordena por esa columna, ascendente → descendente → orden
  original. Los textos se comparan sin distinguir mayúsculas, los vacíos (`None`) van siempre al
  final y los empates conservan el orden original. El orden se calcula una vez y se memoriza
  mientras `rows` sea el mismo objeto y no cambie de longitud: si cambian los datos, pasa una
  secuencia nueva en vez de modificarla en su sitio.
- **Redimensionar:** arrastrar el borde derecho de una cabecera cambia el ancho de su columna (sin
  bajar de `min_width`). Si las columnas no caben, la tabla se desplaza en horizontal.
- El orden y los anchos se guardan por `key`. Para leerlos o fijarlos desde fuera, pasa tus
  `Signal`: `sort` con `(key_de_columna, descendente)` o `None`, y `widths` con
  `{key_de_columna: ancho}` (las que falten usan `Column.width`).
- `on_row_click(fila)` hace las filas pulsables. `striped` alterna el fondo de las filas y `empty`
  es el texto que se muestra sin filas.
- Sin `height` ni `max_height`, ocupa el espacio libre (`grow=1`), como un `scroll`.
- En los tests, las cabeceras tienen key `"{key}/h/{columna}"`, los bordes
  `"{key}/resize/{columna}"`, las filas `"{key}/row/{índice en rows}"` y el cuerpo desplazable
  `"{key}/body"`.

#### `Column(key, title=None, *, width=160, min_width=48, align="start", value=None, format=None, cell=None, sortable=True, resizable=True)`

| Campo | Descripción |
|---|---|
| `key` | Identifica la columna. Sin `value`, el valor de cada celda es `fila[key]` en un dict, `getattr(fila, key)` en un objeto o la posición de la columna en una tupla o lista. |
| `title` | Texto de la cabecera. Por defecto, la `key`. |
| `width` / `min_width` | Ancho inicial y mínimo al redimensionar, en píxeles. |
| `align` | `"start"`, `"center"` o `"end"` (números). |
| `value` | `value(fila)`: valor de la celda, que es lo que se ordena. |
| `format` | `format(valor)`: texto que se muestra. Por defecto, `str(valor)` (`None` se muestra vacío). |
| `cell` | `cell(fila)`: elemento que sustituye al texto (badges, avatares, botones). La ordenación sigue usando el valor. |
| `sortable` / `resizable` | Si la cabecera ordena al pulsarla / si su borde se puede arrastrar. |

### `tooltip(child, tip)`

Muestra `tip` en una burbuja al dejar el puntero **medio segundo** sobre `child`. Aparece debajo
(o encima, si no cabe), sin salirse de la ventana, se oculta al hacer clic o pulsar una tecla, y
no intercepta el ratón. Es lo mismo que pasar `tooltip="..."` a cualquier elemento:

```python
tooltip(button("Guardar", save), "Ctrl+S")
image("info.svg", width=16, tooltip="Se actualiza cada hora")
```

La burbuja usa los colores heredables `tooltip_bg` y `tooltip_color`, que por defecto invierten el
tema (`$text` sobre `$background`), así destaca en claro y en oscuro.

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
| `bg_hover` | color | Fondo con el cursor encima (requiere `on_click` u `on_drag`). Transición animada. |
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
| `tooltip` | texto | Texto de ayuda que aparece al dejar el puntero encima. Ver [`tooltip`](#tooltipchild-tip). |
| `cursor` | `"default"`, `"pointer"`, `"text"`, `"grab"`, `"grabbing"`, `"col-resize"`, `"row-resize"` | Cursor del ratón sobre el elemento y sus hijos (salvo que un hijo fije otro). Durante un `on_drag` se mantiene el del elemento arrastrado. |
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
| `tooltip_bg`, `tooltip_color` | — | colores de la burbuja de los tooltips | `$text`, `$background` | *H* |
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
