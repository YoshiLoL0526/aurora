# Changelog

Todos los cambios relevantes de Aurora se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[Versionado Semántico](https://semver.org/lang/es/). Mientras la versión sea `0.x`, cualquier
versión menor puede incluir cambios incompatibles, que siempre se señalarán aquí.

## [Sin publicar]

### Añadido

- **Movimiento por defecto en los componentes**: `switch`, `checkbox`, `tabs` y `select` animan
  sus cambios sin declarar nada — el knob se desliza, la marca de la casilla entra
  encogiéndose, el subrayado de las pestañas funde y el menú del desplegable aparece
  deslizándose y se va fundiéndose. Comparten una escala común de duraciones cortas.
  - `App(view, motion=False)` o la variable de entorno `AURORA_MOTION=0` lo desactivan para
    toda la app (tests de snapshot, equipos que lo prefieren sin movimiento).
  - Los efectos de entrada no se reproducen en el primer frame ni en `render_png`: las
    capturas y la documentación siguen siendo deterministas.
- `examples/studio.py` aprovecha las animaciones: las páginas se funden al cambiar, el modal y
  el toast entran y salen, las tarjetas del tablero y las barras de progreso se deslizan.
- **Componentes nuevos** (con las animaciones anteriores ya puestas):
  - `dialog`: modal completo — fondo, tarjeta centrada, cierre con clic fuera o Esc, foco dentro
    de la tarjeta al abrirse y atrapado, y entrada/salida animadas. Devuelve `None` cerrado.
  - `toast`: aviso flotante abajo a la derecha que se descarta con un clic (enlazado a un
    `Signal[str | None]`) y entra deslizándose.
  - `progress`: barra de progreso de 0 a `max` que crece hasta su nuevo valor y admite color del
    tema o gradiente.
  - `pages`: una vista por valor de un `Signal` con transición entre páginas y su propio scroll.
- `examples/studio.py` usa los componentes nuevos: `dialog`, `toast`, `progress` y `pages`
  sustituyen sus versiones locales y montadas a mano.
- **Vaivén perpetuo `animate.pulse()`**: opacidad que baja hasta `floor` y vuelve, sin terminar.
  Se pasa en la propiedad `pulse` de un elemento; con `App(motion=False)` queda fijo.
- **El color del texto ahora anima** con `transition` (antes se cambiaba de golpe): los párrafos
  se rehacen con el color interpolado mientras dura la transición. El color heredado de un
  contenedor no se propaga a los hijos: para animarlo, el texto necesita su `transition`.
- **`top`/`right`/`bottom`/`left` aceptan porcentajes** (`left="50%"`), resueltos contra la caja
  de relleno del padre. Es lo que permite anclar pulgares y barras por fracción sin medir nada.
- **Componentes nuevos** con movimiento por defecto:
  - `radio`: grupo de opciones; el punto interior entra encogiéndose.
  - `segmented`: selector con pulgar deslizante (usa los porcentajes en `left`).
  - `slider`: deslizador arrastrable (`width` en píxeles) con relleno y pulgar que siguen el valor.
  - `spinner`: tres puntos que laten en cadena (`pulse`); nunca queda en reposo.
  - `skeleton`: bloques con la forma del contenido que llega, latiendo despacio.
- Las pestañas (`tabs`) funden también el color de su texto, y `examples/studio.py` usa el
  `segmented` del catálogo.
- **`overflow="hidden"`**: el contenido que se sale de su caja se recorta (pintado y clics) sin
  tocar el layout. Con `shrink=0` en el hijo, desborda en vez de aplastarse: es la base del
  despliegue del acordeón.
- **Componentes nuevos**:
  - `menu`: lista de acciones que se abre desde un disparador, en superposición, con cierre al
    elegir, al hacer clic fuera o con Esc.
  - `accordion`: secciones que se despliegan con altura animada y recorte, y se quedan montadas al
    plegarse (conservan su estado).
  - `field`: etiqueta + control + mensaje de ayuda o error (`$danger`).
- `examples/studio.py` estrena los tres: `field` en el formulario de nueva tarea, `menu` en las
  tarjetas del tablero y un acordeón de «Zona de peligro» en Ajustes.

### Cambiado

- **Los ejemplos se actualizan a lo último de la librería**: `hello.py` muestra la versión real en
  su insignia y ajusta el paso del contador con un `slider`; `animate.py` usa `dialog` para el
  modal, lleva el progreso en una barra y funde el color del texto al completar; `canvas.py`
  mueve la carga del clúster con un deslizador; `charts.py` elige la forma del gráfico de cierres
  con un `segmented`; `table.py` pinta avatares en las celdas; `brand.py` refleja el ejemplo del
  README; y `studio.py` añade `radio` y `slider` a Ajustes (densidad del tablero y objetivo
  semanal) y su número de versión deja de estar escrito a mano. La galería de la documentación
  gana capturas de esos estados.
- **Reorganización interna en módulos** (misma API pública):
  - `python/aurora/components.py` pasa a ser el paquete `python/aurora/components/`, con un
    módulo por familia (`basic`, `forms`, `navigation`, `overlays`, `feedback` y `lists`).
  - El núcleo nativo se reparte por fases y dominios de entrada: `src/render.rs` → `src/render/`,
    `src/runtime.rs` → `src/runtime/` y `src/chart.rs` → `src/chart/`.
  - Los iconos SVG y el parseo de las variables `AURORA_*` quedan compartidos en `_icons.py` y
    `_flags.py`; `menu` y `select` comparten la mecánica del desplegable (`_dropdown.py`).
  - Con esa unificación, el desplegable de `select` cierra con Esc/Enter «limpios» (sin
    modificadores), como `menu` y `dialog`; antes también cerraba con Shift+Esc o Ctrl+Enter.

### Corregido

- `examples/brand.py` ya no falla al imprimir «✓» en una consola de Windows sin UTF-8 (como ya
  hacía `studio.py`), así que `uv run examples/brand.py` termina con código 0 y regenera el banner
  y el logo.
- En un `textarea`, `Ctrl+Inicio`/`Ctrl+Fin` (Windows/Linux) y `Cmd+Inicio`/`Cmd+Fin`
  (macOS) saltan al principio o al final del texto; sin modificador, Inicio/Fin siguen
  yendo al borde de la línea. Antes, en macOS `Cmd+Inicio` no hacía el salto.
- El test de la rejilla del `chart` contaba cualquier píxel parecido al borde: en Linux,
  el anti-aliasing del trazo o de la fuente producía falsos positivos. Ahora compara el
  total de píxeles de la rejilla entre `grid=True` y `grid=False`.

## [0.3.0] — 2026-10-16

### Añadido

- **Documentación publicada con ejemplos vivos** en <https://yoshilol0526.github.io/aurora/>
  (MkDocs Material, desplegada en GitHub Pages en cada cambio de `main`):
  - Los bloques ```` ```python live ```` se **ejecutan al construir** la documentación y debajo
    se publica la captura que renderiza Aurora, en tema claro y oscuro según el del lector. Un
    ejemplo que falla rompe la construcción y `tests/test_docs.py`, así que no pueden quedarse
    desfasados.
  - Admiten programas completos, fragmentos que terminan en un elemento, pasos que continúan el
    programa anterior (`continue`), scripts de `examples/` (`file=`) y código oculto para
    preparar un estado (`# oculto`).
  - La guía, la referencia de componentes y una **galería** con los ejemplos del repositorio
    usan ejemplos vivos.

- **Hot reload que conserva el estado.** Con `aurora dev app.py`, `AURORA_RELOAD=1` o
  `App(view, reload=True)`, al guardar el script o un módulo local la ventana se actualiza con el
  código nuevo sin cerrarse:
  - Se vuelven a ejecutar el módulo cambiado, los módulos de la app que usan algo suyo y el
    script principal; la app en marcha adopta la `view` y el `theme` nuevos.
  - Los `Signal` que siguen en el mismo sitio (global, atributo de un objeto de la app, dict o
    lista) conservan su valor y su identidad: hilos, corrutinas y otros módulos no notan nada.
  - Si el código nuevo no compila o falla, los módulos vuelven a como estaban y la ventana
    muestra el traceback hasta que se guarda una versión que funciona; una excepción en `view()`
    también se muestra en vez de cerrar la app.

  Para tests, `app.watch(module)` devuelve el `Reloader` sin hilo vigilante
  (`reloader.check()` y el siguiente frame del piloto aplica los cambios).

- **Inspector visual del árbol y profiler de frames.** Con `App(view, inspector=True)` o la
  variable de entorno `AURORA_INSPECTOR=1`, F12 acopla un panel a la derecha de la ventana:
  - **Árbol** navegable (virtual, con ramas plegables) con tipo, key y texto de cada nodo; al
    elegir uno se ven su caja, su estilo resuelto, su texto y sus eventos, y se resalta sobre la
    interfaz.
  - **Modo selección** (Ctrl+Mayús+C o el botón ⌖): pasar el ratón resalta el nodo bajo el
    puntero con su padding y su tamaño, sin llamar a Python; un clic lo elige sin llegar a la app.
  - **Profiler de frames**: coste por fases de los últimos 240 frames en barras apiladas frente
    al presupuesto de 60 fps, con último, media, p95, máximo y desglose por fase.

  Desactivado no cuesta nada. El panel está hecho con las primitivas de Aurora; el núcleo pone el
  modo selección, el resaltado y el historial (`_core.inspection()`). En tests,
  `app.pilot(inspector=True)` y `Pilot.inspection`.
- `Pilot.stats["total"]`: suma de las fases del frame.
- Cursor `"crosshair"` en la propiedad de estilo `cursor`.

- **`aurora build`**: empaqueta una app en un ejecutable distribuible con un comando (un solo
  archivo, una carpeta o una `.app` en macOS), sin consola, con icono y recursos incluidos.
  Se configura con opciones o en `[tool.aurora.build]` de `pyproject.toml` y valida la
  configuración antes de empezar. Usa PyInstaller, como dependencia opcional
  (`aurora-ui[build]`). También como `python -m aurora build`.
- `resource(path)`: ruta de un recurso de la app relativa al script principal, que funciona igual
  con Python y dentro del ejecutable empaquetado.

- **Animaciones declarativas** (`aurora.animate`), interpoladas en Rust sin llamar a Python en
  cada frame. Cuatro propiedades de estilo nuevas:
  - `transition=animate.spring()` o `animate.tween(0.2)`: los cambios de `bg`, `border_color`,
    `opacity` y `radius` entre reconstrucciones se animan desde lo que se ve (cambiar de destino
    a medias no da saltos).
  - `animate_layout=True`: el elemento se desliza a su nueva caja cuando el layout lo mueve
    (otros que aparecen, se van o se reordenan); fondo, borde y sombra cambian de tamaño con él.
  - `enter=` y `exit=` con los efectos `animate.fade()`, `animate.slide(x, y)`,
    `animate.zoom(scale)` y `animate.effect(...)` (opacidad, desplazamiento y escala). Lo que
    sale se pinta como una instantánea que ya no ocupa sitio ni recibe eventos; si vuelve antes
    de terminar, entra desde donde estaba. Las entradas no se reproducen en el primer frame.
  - Curvas: muelle físico (`stiffness`, `damping`, `mass`) o interpolación con easing de CSS,
    ambas con `delay` para escalonar.

  Las animaciones se repintan por zonas como el resto (cada frame coincide con un repintado
  completo) y `pilot.frame()`/`pilot.settle()` las esperan, salidas incluidas.

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
- **Empaquetado para PyPI**: las capturas del README se referencian con URLs absolutas (antes
  relativas), así que se ven también fuera de GitHub; `Cargo.toml` declara `repository`,
  `homepage` y `documentation` (ya no avisa al empaquetar); y el sdist se limita con el whitelist
  `include` de `Cargo.toml` a lo necesario para recompilar el paquete (antes arrastraba
  `.github/`, `docs/`, `examples/`, `benchmarks/` y `tests/`: 1,3 MB → 195 KB).

### Corregido

- La ventana ya no muestra un destello blanco al abrirse: se crea oculta y aparece con su primer
  frame ya pintado, en vez de enseñar el fondo vacío del sistema mientras arranca la GPU y se
  construye la vista.

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

[Sin publicar]: https://github.com/YoshiLoL0526/aurora/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/YoshiLoL0526/aurora/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/YoshiLoL0526/aurora/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/YoshiLoL0526/aurora/releases/tag/v0.1.0
