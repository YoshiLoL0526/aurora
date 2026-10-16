# Changelog

Todos los cambios relevantes de Aurora se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[Versionado Semántico](https://semver.org/lang/es/). Mientras la versión sea `0.x`, cualquier
versión menor puede incluir cambios incompatibles, que siempre se señalarán aquí.

## [Sin publicar]

### Añadido

- **`table(rows, columns, *, key, ...)`**: tabla de datos con cabecera fija, **ordenación** (clic
  en la cabecera: ascendente → descendente → original; vacíos al final, orden estable y
  memorizado), **columnas redimensionables** (arrastrando el borde de la cabecera, con
  `min_width` y desplazamiento horizontal si no caben) y filas **virtualizadas** sobre
  `virtual_list` (100 000 filas sin coste al desplazarse). Las filas pueden ser dicts, tuplas u
  objetos; `Column` define título, ancho, alineación, `value`, `format`, `cell` (cualquier
  elemento) y si ordena o se redimensiona. Orden y anchos se guardan por `key` o en `Signal`
  propios (`sort`, `widths`); `on_row_click(fila)` hace las filas pulsables. Ejemplo en
  `examples/table.py`.
- `on_drag` en cualquier elemento, con `DragEvent` (`phase`: `"start"`, `"move"`, `"end"`; `x`,
  `y`; `dx`, `dy` desde donde se pulsó): el elemento recibe el arrastre hasta soltar aunque el
  puntero salga de su caja, y un arrastre no completa el clic.
- Propiedad de estilo `cursor` (`"pointer"`, `"text"`, `"grab"`, `"grabbing"`, `"col-resize"`,
  `"row-resize"`, `"default"`).
- `Pilot.drag(key, dx, dy, steps=4)` y `Pilot.cursor`.

- **Downsampling (LTTB) en Rust:** los `chart` reducen cada serie a ~2 puntos por píxel al
  grabarla (*Largest-Triangle-Three-Buckets*), tramo a tramo (los `NaN` cortan la línea) y con
  presupuesto por ancho en pantalla, así que los picos se conservan (con x desordenada, como una
  curva cerrada, el presupuesto es el ancho entero). Un gráfico de **millones de puntos** se graba
  en milisegundos: con x ordenada (y sin huecos en x) solo se recorren los índices visibles, más
  un punto de margen a cada lado cuyo segmento se corta justo en el borde. Los datos se siguen leyendo sin copiarlos y solo se releen cuando
  la ventana o los datos cambian.
- **`chart(..., zoom=True)`**: zoom y pan sobre el eje x. La rueda acerca y aleja con el puntero
  como ancla (el dato bajo el cursor no se mueve), el arrastre y la rueda horizontal desplazan la
  ventana y el doble clic vuelve a la vista completa; el eje y se ajusta a lo visible salvo que
  fijes `y_min`/`y_max`. Al llegar a un tope, la rueda pasa al `scroll` de fuera, y el cursor
  cambia a "agarrar" sobre un gráfico con zoom. La ventana es estado por `key` que sobrevive a las
  reconstrucciones y `Pilot.chart_view(key)` la lee en los tests. El ejemplo de
  `examples/charts.py` incluye una señal de un millón de puntos con zoom.
- `chart(y, *, kind="line", **estilo)`: gráficos nativos de **línea**, **área**, **barras** y
  **dispersión**, con los ejes (ticks redondos), la rejilla y la leyenda calculados solos. Los
  datos se leen **sin copiarlos**, con el protocolo de búfer: arrays de numpy (`f32`/`f64` y
  enteros, en cualquier orden de bytes, contiguos o con *strides*: vistas, matrices por columnas,
  arrays en orden Fortran), `array.array`, `memoryview` y Series/DataFrames de polars o pandas
  (vía `to_numpy`), además de listas (también de escalares de numpy). Varias series con una lista, un array 2-D o un DataFrame; `color` (un color o la paleta
  del tema por serie), `names` (leyenda), `labels` (categorías), `x`, `y_min`/`y_max`, `grid`,
  `stroke_width`, `point_size` y `bar_width` (las barras de varias series se agrupan). El dibujo se
  graba en un `Picture` de Skia que se repinta sin releer los datos: solo se vuelve a grabar si
  cambian los datos u opciones, o la caja del gráfico. Ejemplo en `examples/charts.py`.
- `Pilot.stats["draw"]` incluye también el grabado de los `chart`.
- `canvas(draw, **estilo)`: lienzo de dibujo inmediato. `draw(c)` recibe un `Canvas` con su
  tamaño (`c.width`, `c.height`) y dibuja rectángulos, círculos, elipses, arcos, líneas,
  polilíneas, polígonos, trazados libres (`Path`) y texto, con relleno, trazo, guiones,
  transformaciones y recortes; los colores aceptan tokens del tema. Los comandos cruzan al núcleo
  en un solo lote y se graban en un `Picture` de Skia que se repinta sin volver a Python. `draw`
  se llama tras el layout, al reconstruirse la vista o cambiar el tamaño; dentro de un
  `@component`, solo si cambia algún `Signal` que lea. Los puntos admiten arrays de numpy sin
  recorrerlos en Python. Ejemplo en `examples/canvas.py`.
- `Pilot.stats["draw"]`: coste de las funciones `draw` de los `canvas` en el último frame.
- Backend GPU: la ventana pinta con Skia sobre Vulkan (Windows y Linux) o Metal (macOS), y vuelve a
  la CPU (softbuffer) si la GPU no arranca o se pierde el dispositivo. El repintado parcial se
  conserva con un lienzo persistente en la GPU. `App.run(backend="auto" | "gpu" | "cpu")` y la
  variable de entorno `AURORA_BACKEND` eligen el backend.
- `Pilot.stats`: coste del último frame por fases (`build`, `parse`, `layout`, `paint`), número de
  nodos y si se reconstruyó la vista.
- Suite de benchmarks reproducible (`benchmarks/run.py`): lista de 10 000 filas, dashboard de 50
  paneles y escritura en un formulario de 500 filas, con mediana y p95 por fase, salida JSON,
  comparación con una medición anterior (`--compare`) y ejecución en CI con resumen en cada build.
- `Pilot.stats["layout_cached"]`: si el frame reutilizó el layout del anterior.
- Reactividad de grano fino con `@component`: un componente no se reconstruye si sus argumentos
  son iguales y no cambió ningún `Signal` que leyera (al construirse o en sus textos con lambda).
  Reutiliza el mismo `Element`, su serialización y el nodo ya parseado en el núcleo. En la lista de
  10 000 filas con filas como componentes, cambiar la selección pasa de ~0,8 s a ~0,19 s.
- `virtual_list(count, item, item_height=..., key=...)`: lista de filas de alto fijo que solo
  construye las visibles. Con 100 000 filas, reconstruir cuesta menos de 1 ms y las filas nuevas
  aparecen en el mismo frame del desplazamiento.
- `on_scroll` en los contenedores `scroll`, con `ScrollEvent` (`x`, `y`, `width`, `height`): se
  llama cuando cambian el desplazamiento o la zona visible, sin reconstruir la vista por sí solo.
- `Pilot.stats["style"]` (coste de la fase de estilo) y `Pilot.stats["damage"]` (zona repintada en
  el último frame, o `None`). La suite de benchmarks muestra la fase `style`.
- Comprobación de tipos con [ty](https://docs.astral.sh/ty/) en la CI, junto a ruff, sobre la
  librería, los tests, los ejemplos y los benchmarks.

### Cambiado

- **Incompatible:** Python ≥ 3.11 (antes 3.10). Los `chart` leen los arrays sin copiarlos con el
  protocolo de búfer, que la API estable (abi3) expone desde 3.11; el wheel sigue siendo uno por
  plataforma y arquitectura.
- El layout se cachea entre frames: si no cambia el árbol, el tamaño ni el texto de los campos
  (hover, scroll, animaciones, parpadeo del cursor), solo se vuelve a pintar. En una lista de
  10 000 filas un frame sin reconstrucción pasa de ~1,2 s a ~30 ms.
- Al reconstruir la vista se reutiliza el shaping de los párrafos que no cambiaron (por contenido,
  no por key) junto con sus mediciones, que además se memorizan dentro de cada layout. El layout
  de esa misma lista al reconstruir baja de ~1,06 s a ~0,3 s.
- Al reconstruir, el árbol de layout se reconcilia por key en vez de rehacerse: solo se recalculan
  las ramas cuyo estilo de layout, texto, imagen o hijos cambiaron. Un cambio que solo afecta a la
  pintura (fondo, color de borde, sombra…) no rehace el layout. En la lista de 10 000 filas el
  layout al reconstruir baja a ~60 ms, y en el formulario de 500 filas a ~2 ms por tecla.
- Invalidación por fases (estilo → layout → composición → pintura): cada cambio rehace solo las
  fases que le afectan.
  - Al reconstruir, el árbol nuevo se compara con el anterior: si nada afecta a la geometría
    (colores, fondos, opacidad, color de un texto…), no se rehace el layout y solo se repintan
    esos nodos. Cambiar la selección en la lista de 10 000 filas ya no hace layout (~57 ms): la
    comparación cuesta ~12 ms.
  - Desplazar un `scroll` solo recoloca su capa: no rehace el layout ni las regiones.
  - Solo se repinta la zona que cambió (hover, transiciones, cursor, tooltip, capas movidas),
    sin recorrer lo que queda fuera, y la ventana solo presenta esa zona. Un frame sin cambios no
    pinta nada. En la lista de 10 000 filas, hover pasa de ~30 ms a ~1 ms, desplazar de ~36 ms a
    ~1,5 ms y un frame ocioso de ~31 ms a menos de 1 ms.
  - Un `on_scroll` que reconstruye la vista (listas virtuales) ya no obliga a pintar dos veces el
    mismo frame.
  - Un layout ya no repinta la ventana entera: se comparan por key las regiones nuevas con las
    anteriores y solo se repintan los nodos que cambiaron de geometría, de aspecto o de orden de
    pintura, más los que aparecen o desaparecen. Al escribir en el formulario de 500 filas, pintar
    pasa de ~0,42 ms a ~0,16 ms. Un cambio de tamaño de la ventana, un cambio que afecta a más de
    la mitad de los nodos o una zona dañada de más del 70 % de la ventana se siguen pintando
    enteros.
- **Incompatible:** un elemento sin `key` recibe la de su padre seguida de su posición
  (`"fila-7/0"`), no la ruta completa desde la raíz. Los hijos de un elemento con key conservan su
  identidad (hover, foco, scroll) aunque el padre cambie de sitio. Un test que buscara un nodo por
  su ruta (`"0/1/2"`) tiene ahora como prefijo la key de su ancestro con key más cercano.
- Crear elementos y resolver tokens de tema es algo más rápido (un solo recorrido de los argumentos).

## [0.2.0] — 2026-10-15

Apps de verdad: scroll, teclado y foco, campos de texto, imágenes y más componentes.

### Añadido

- Componentes `divider`, `avatar`, `checkbox`, `switch`, `tabs` (con ← →) y `select` (desplegable en
  capa superior, con scroll, Esc y ↑ ↓), enlazados a `Signal` donde aplica.
- `tooltip(child, tip)` y la propiedad `tooltip`: burbuja tras medio segundo de hover, colocada
  dentro de la ventana, con colores heredables `tooltip_bg` y `tooltip_color`; `Pilot.tooltip`.
- Primitiva `image(src, fit=...)`: PNG, JPEG, WebP, GIF, BMP, ICO y SVG (vectorial) desde una ruta
  o desde `bytes`, con proporción automática, `fit` (`contain`, `cover`, `fill`, `none`), recorte a
  las esquinas redondeadas, caché de decodificación que detecta cambios en disco y errores claros
  (`FileNotFoundError`, `ValueError`).
- Campos de texto `text_input` y `textarea`, enlazados en los dos sentidos a un `Signal[str]`:
  cursor que parpadea, selección con teclado y ratón (doble y triple clic), recorrido por grafemas y
  palabras, portapapeles, deshacer/rehacer agrupando lo escrito, composición con IME, placeholder,
  `on_submit`, desplazamiento horizontal en una línea y crecimiento con el contenido en varias.
- Propiedades `placeholder_color` y `selection_color`; cursor de texto del ratón sobre los campos.
- `Pilot.type()`, `ime_preedit()`, `ime_commit()`, `selection()` y `clipboard`.
- Teclado y foco: Tab / Shift+Tab en orden de pintura (atrapado dentro de barreras `capture`),
  activación con Enter y Espacio, anillo de foco animado solo al navegar con teclado
  (`focus_color`, heredable) y desplazamiento automático del `scroll` para mostrar el foco.
- `on_key` con `KeyEvent` (`key`, `text`, modificadores, `matches("mod+s")`), que burbujea desde el
  foco hasta la raíz; `on_focus`, `on_blur`, `focusable` y `autofocus`.
- Desplazamiento con flechas, RePág/AvPág, Inicio/Fin y Espacio.
- `Pilot.press()`, `key_down()`, `key_up()`, `focus()` y `focused`.
- Contenedor `scroll(axis="y" | "x" | "both")`: recorte, rueda con desplazamiento suave, trackpad,
  encadenado al `scroll` exterior en el límite y barra superpuesta que se oculta sola y se puede
  arrastrar. La posición se conserva entre reconstrucciones.
- Propiedades `min_height`, `max_height` y `scrollbar_color`.
- `Pilot.wheel()`, `Pilot.scroll()` y `Pilot.scroll_offset()`.
- `app.pilot()`: piloto headless para tests de interacción (`click`, `move_to`, `hovered`, `rect`,
  `settle`, `png`…) que usa el mismo runtime que la ventana.
- `Signal.set` es seguro desde cualquier hilo y despierta el bucle de eventos: la ventana se
  actualiza sin esperar a un evento del usuario.
- `app.spawn(coro)`: ejecuta corrutinas en un bucle `asyncio` en segundo plano.
- Propiedad `layer="overlay"`: pinta un elemento y le da los eventos por encima de todo el árbol.
- Manejadores genéricos: cualquier argumento `on_<evento>` de un elemento es un manejador.

### Cambiado

- `Element.to_spec()` serializa los manejadores en `"handlers": {"click": fn}` en lugar de
  `"on_click"`. `Element.on_click` sigue disponible como propiedad de solo lectura.
- El núcleo separa el estado de la app (`Runtime`) del bucle de ventana.
- El hit-testing respeta el recorte de los contenedores `scroll`.
- La demo `studio.py` desplaza el contenido de cada página y estrena búsqueda en el tablero, un
  formulario de nueva tarea (Ctrl+N y el botón lo abren en vez de añadir una tarea de ejemplo),
  una página de Ajustes y tooltips.
- Nuevas dependencias del núcleo: `arboard` (portapapeles) y `unicode-segmentation`. Las features de
  `skia-safe` cambian por sistema (`svg`, `webp` y, fuera de macOS, `ganesh` + `vulkan`) para
  seguir usando binarios precompilados de Skia.

### Corregido

- `examples/studio.py --png` ya no falla en consolas de Windows sin UTF-8.

## [0.1.0] — 2026-10-15

Primera versión: la base del framework.

### Añadido

- Núcleo nativo en Rust expuesto como `aurora._core` (PyO3 + maturin, wheel abi3 para Python ≥ 3.10).
- Layout flexbox con Taffy: `direction`, `gap`, `padding`, `align`, `justify`, `grow`, `shrink`,
  `wrap`, tamaños en píxeles o porcentaje, `min_width`/`max_width` y `position="absolute"` con
  `top`/`right`/`bottom`/`left`.
- Render con Skia: esquinas redondeadas, bordes, sombras difuminadas, gradientes lineales y opacidad.
- Texto con shaping real, fallback de fuentes, herencia de estilos de texto, alineación por baseline,
  `max_lines` con elipsis y `text_align`.
- Ventana nativa con winit; el bucle de eventos corre sin el GIL.
- Estados hover y pressed animados en el núcleo (`bg_hover`, `bg_pressed`, `press_scale`).
- Hit-testing con burbujeo al ancestro interactivo y barreras de eventos (`capture`).
- API declarativa: `box`, `row`, `column`, `text`, `spacer`, hijos con `[...]`, `key` y `on_click`.
- `Signal` para el estado reactivo.
- Temas con tokens (`"$primary"`), temas `MIDNIGHT` y `DAYLIGHT`, y tema reactivo vía `Signal[Theme]`.
- Componentes: `button` (variantes `primary`, `soft`, `ghost`), `card`, `badge` y `stat`.
- `App.render_png()` para renderizar sin ventana.
- Ejemplos: `hello.py`, `studio.py` (demo completa) y `brand.py` (genera las imágenes del README).
- Documentación: guía, referencia, arquitectura, visión y roadmap.

[Sin publicar]: https://github.com/<usuario>/aurora/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/<usuario>/aurora/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/<usuario>/aurora/releases/tag/v0.1.0
