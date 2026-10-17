# Arquitectura

Este documento explica cómo funciona Aurora por dentro y **por qué** está diseñado así. Está
pensado para contribuidores y para quien quiera entender qué pasa entre un `Signal.set()` y un
píxel en pantalla.

## Idea central

> **Python describe, Rust ejecuta. La frontera se cruza poco y con mucha información.**

Llamar de Python a código nativo es barato una vez, y carísimo diez mil veces por frame. Por eso
Aurora nunca expone a Python operaciones de bajo nivel ("dibuja este rectángulo", "mide este
texto"). Python produce un **árbol de descripción completo**, y Rust hace todo el trabajo pesado
sobre ese árbol sin volver a consultar al intérprete.

## Mapa del código

```
python/aurora/
├── __init__.py      App: une la vista, el tema y el núcleo nativo
├── elements.py      Element y primitivas (box, row, column, text, spacer)
├── canvas.py        canvas(), Canvas y Path: graba comandos de dibujo en un lote
├── charts.py        chart(): gráficos de línea, área, barras y dispersión
├── components/      Componentes con estilo, solo con primitivas (un módulo por familia)
│   ├── basic.py     Botón, tarjeta, insignia, métrica, separador y avatar
│   ├── forms.py     Campos de texto, casillas, interruptores, radio y deslizador
│   ├── navigation.py  Pestañas, páginas, selector segmentado y acordeón
│   ├── overlays.py  Menú, diálogo, tooltip y desplegable (`select`)
│   ├── feedback.py  Progreso, spinner, esqueleto y toast
│   └── lists.py     Lista virtualizada; `_shared`, `_state` y `_dropdown` son internos
├── inspector.py     Panel del inspector y del profiler, acoplado a la vista con F12
├── signal.py        Estado reactivo
├── theme.py         Design tokens y temas MIDNIGHT / DAYLIGHT
├── _icons.py        Iconos SVG compartidos (casilla, cheurón y flechas de orden)
└── _core.pyi        Stubs del módulo nativo

src/                 (crate aurora_core → módulo aurora._core)
├── lib.rs           Funciones expuestas a Python: render_png, run, wake, Pilot
├── spec.rs          Árbol de Python (dicts) → Node tipado; herencia de estilos de texto
├── color.rs         Parseo de colores e interpolación
├── render/          Motor por fases del frame (un módulo por fase)
│   ├── mod.rs       Engine: estado, update (layout y composición) y orquestación
│   ├── style.rs     Fase de estilo y animaciones declarativas (transiciones, entradas/salidas)
│   ├── layout.rs    Árbol de Taffy y su reconciliación incremental
│   ├── geom.rs      Geometría, regiones de hit-testing, capas y zonas dañadas
│   ├── paint.rs     Pintura por zonas (repintado parcial) y recorrido del árbol
│   ├── draw.rs      Dibujo de cajas, imágenes, barras y anillo de foco
│   ├── text.rs      Párrafos de Skia («shaping»), medición y campos de texto
│   └── png.rs       Render a PNG sin ventana
├── runtime/         Estado de la app en marcha (un módulo por dominio de entrada)
│   ├── mod.rs       Runtime: árbol, despacho de eventos, wake y frame (update+paint)
│   ├── pointer.rs   Hover, clics y arrastres (barras, gráficos y `on_drag`)
│   ├── keyboard.rs  Manejadores `on_key`, Tab/Enter/Espacio y flechas
│   ├── editing.rs   Campos de texto: edición, portapapeles, IME y cursor
│   ├── focus.rs     Foco (`on_focus`/`on_blur`), Tab y revelado del nodo
│   ├── wheel.rs     Rueda, zoom de gráficos y barras de desplazamiento
│   └── clipboard.rs Portapapeles del sistema o en memoria
├── scroll.rs        Estado de los contenedores scroll: desplazamiento, suavizado, barra
├── inspect.rs       Inspector y profiler: modo selección, historial de frames, estado prestado a Python
├── keys.rs          KeyEvent y parseo de combinaciones ("ctrl+s", "mod+k")
├── edit.rs          Modelo de edición puro: texto, cursor, selección, deshacer, grafemas
├── input.rs         Estado de los campos de texto y geometría de cursor y selección
├── image.rs         Decodificación de imágenes (raster y SVG), caché y encaje (fit)
├── canvas.rs        Lote de comandos de un canvas → Picture de Skia; cuándo volver a grabarlo
├── chart/           Gráficos nativos (un módulo por fase)
│   ├── mod.rs       El modelo: `Chart`, `Series`, `ChartKind`
│   ├── parse.rs     Vista sin copia de los búferes de Python → `Chart`
│   ├── view.rs      Ventana visible (zoom/pan) y reducción de series (LTTB)
│   ├── scale.rs     Escala de los ejes: pasos, ticks y etiquetas
│   ├── paint.rs     Dibujo de ejes, rejilla, leyenda y series
│   └── cache.rs     Grabado perezoso (`Charts`): cuándo volver a grabar
├── window.rs        Bucle de ventana (winit) sobre Runtime
├── surface/         Trait Surface: dónde se pinta y presenta cada frame
│   ├── cpu.rs       Skia raster en el framebuffer de softbuffer
│   ├── vulkan.rs    Skia Ganesh sobre Vulkan (vulkano), Windows y Linux
│   └── metal.rs     Skia Ganesh sobre Metal (CAMetalLayer), macOS
└── pilot.rs         Piloto headless sobre Runtime para tests de interacción
```

## Ciclo de vida de un frame

```
           ┌────────────────────────── Python (con el GIL) ──────────────────────────┐
 evento ─► │ callback del usuario ─► Signal.set() ─► view() ─► Element ─► to_spec()   │
           └──────────────────────────────────────────────────────────┬──────────────┘
                                                                      │ dict anidado (1 cruce)
           ┌────────────────────────── Rust (sin el GIL) ─────────────▼──────────────┐
           │ spec::parse     → Node tipado, herencia de text props, keys estables    │
           │ Engine::restyle → estilo: qué cambió y en qué fase entra cada cambio    │
           │ Engine::tick    → avanza transiciones hover/pressed (dt real)           │
           │ Engine::update  → layout (Taffy + texto con Skia) y composición (capas) │
           │ Engine::paint   → Skia repinta solo la zona dañada del framebuffer      │
           │ present         → la Surface (GPU o CPU) muestra el frame               │
           └─────────────────────────────────────────────────────────────────────────┘
```

1. **Evento.** winit entrega un `CursorMoved` o `MouseInput`. El bucle corre sin el GIL: mover el
   ratón por encima de la interfaz no toca Python en absoluto.
2. **Hit-testing.** Se busca el nodo pintado más arriba bajo el cursor y se sube por sus ancestros
   hasta el primero interactivo (ver más abajo).
3. **Callback.** Solo al soltar el clic sobre el mismo nodo se toma el GIL, se ejecuta el callback
   y la vista se marca como sucia.
4. **Reconstrucción.** Se llama a `view()` y el árbol resultante se serializa a dicts en un único
   recorrido (`Element.to_spec`), resolviendo tokens de tema y lambdas de texto.
5. **Parseo.** `spec::parse` convierte los dicts en `Node` tipados. Es el único lugar del núcleo
   que conoce la forma de los datos de Python.
6. **Estilo.** El árbol nuevo se compara con el anterior para decidir qué fases hay que rehacer
   (ver [Invalidación por fases](#invalidación-por-fases)).
7. **Layout.** Si hace falta, se actualiza un árbol Taffy paralelo. Los nodos de texto llevan un
   `Paragraph` de Skia ya "shapeado" como contexto: el mismo párrafo se usa para medir y para
   pintar. Tras él se calculan las regiones de hit-testing y las capas.
8. **Composición.** Cada capa (el contenido de un `scroll`) se coloca según su desplazamiento.
9. **Pintura.** `Painter` repinta la zona dañada: sombra → fondo → borde → texto → hijos, sin
   recorrer lo que queda fuera. Skia escribe directamente en la memoria del framebuffer.

## Decisiones de diseño

### Skia sobre Vello o un renderer propio

La calidad visual de una UI depende sobre todo de sus efectos: sombras suaves, blur, gradientes,
antialiasing y, por encima de todo, **el texto**. Skia ofrece todo eso maduro y probado en
producción, incluido un motor de párrafos (`SkParagraph`) con shaping, bidi y fallback de fuentes.
Vello es prometedor pero todavía tiene huecos en filtros y blur. El render queda detrás del
`Engine`, de modo que cambiar de backend no afecta a la API de Python.

### Taffy para el layout

Implementa Flexbox y Grid fielmente a la especificación CSS, lo usan proyectos serios (Zed,
Bevy, Dioxus) y expone una API de medición que encaja con el texto de Skia. Reimplementar
flexbox no aporta nada diferencial.

### Superficies: GPU con CPU de respaldo

La ventana pinta a través del trait `Surface` (`src/surface/`), que solo sabe hacer una cosa:
darle a `Runtime::draw_frame` un lienzo con su edad y presentar el resultado. Hay dos familias:

- **GPU** (por defecto): Skia Ganesh sobre **Vulkan** en Windows y Linux (con
  [vulkano](https://vulkano.rs), que carga el driver en tiempo de ejecución) y sobre **Metal** en
  macOS (una `CAMetalLayer` en la vista de la ventana). Direct3D no se usa porque no hay binarios
  precompilados de Skia con `d3d` + `svg` + `webp`, y Vulkan cubre Windows igual de bien.
- **CPU**: winit + softbuffer + Skia raster. El formato de píxel de softbuffer (`0x00RRGGBB`)
  coincide en little-endian con el N32 (BGRA) de Skia, así que Skia pinta directamente en el
  buffer de la ventana, **sin copias** cuando se repinta entero.

Con `backend="auto"` se intenta la GPU y, si no arranca (sin driver de Vulkan, máquina virtual,
solo un Vulkan por software como llvmpipe), se usa la CPU sin avisar. Si la GPU falla a mitad de
ejecución (dispositivo perdido), la ventana cambia a la CPU y sigue.

Las imágenes que presenta la GPU (swapchain, drawables de Metal) no conservan el frame anterior.
Para no perder el repintado parcial, la GPU pinta en un **lienzo persistente** (`Backbuffer`, una
textura del tamaño de la ventana, siempre con edad 1) y cada frame lo copia entero a la imagen que
se presenta: una copia de textura es casi gratis en la GPU. El frame se presenta con vsync (FIFO
en Vulkan).

### Árbol completo por actualización, con ramas memorizadas

Aurora llama a la vista entera tras cada evento que cambia estado (también tras cada tecla en un
campo de texto). Es una simplificación deliberada:
el coste real es serializar el árbol en Python, que para apps medianas está muy por debajo de un
frame. El diseño ya prepara la reactividad de grano fino de la v0.3:

- Los nodos tienen **identidad estable** (`key` explícita o ruta en el árbol), que ya hoy se usa
  para conservar el estado de animación entre reconstrucciones.
- `Signal` tiene suscriptores, y es el punto natural para registrar dependencias por rama.

### Reactividad de grano fino

Llamar a `view()` es lo que más cuesta en una vista grande: crear los `Element`, serializarlos y
parsear los dicts en Rust. `@component` (`python/aurora/reactive.py`) evita las tres cosas en las
ramas que no cambiaron:

- **Dependencias.** Cada `Signal` tiene una versión que sube en cada `set`. Mientras un componente
  se construye hay un `Frame` en una pila (por hilo) y cada lectura de un `Signal` anota su versión
  ahí. Lo mismo al serializar, porque los textos con lambda se evalúan en `to_spec`. Un componente
  anidado añade sus dependencias al que lo contiene.
- **Memoria por argumentos.** La llamada se reutiliza si sus argumentos (hashables) coinciden con
  una entrada cuyas dependencias siguen en la misma versión: devuelve el mismo `Element`, cuya
  raíz guarda en `_memo` la serialización (válida para el mismo tema). Cada reconstrucción es una
  generación, y las entradas que no se usaron en ella se descartan.
- **Parseo memorizado.** El dict de un componente lleva `memo: True` y llega a Rust como el mismo
  objeto. `spec::Parser`, que vive en el `Runtime`, guarda el `Node` de cada uno por dirección
  (sosteniendo una referencia, para que la dirección no se reutilice) junto con la key de su raíz
  y las propiedades heredadas. Si las tres coinciden, copia el nodo en vez de leer cada propiedad
  de cada dict.
- **Keys.** Un nodo sin key toma la de su padre más su posición, así que el subárbol de un nodo con
  key tiene las mismas keys esté donde esté: un componente con key sigue siendo reutilizable
  aunque se inserten filas antes que él, y el diff del layout lo empareja con su nodo de Taffy.

### Cachés entre frames

Pintar es barato; lo caro es el layout, y sobre todo el texto: hacer el shaping de un párrafo y
maquetarlo en Skia. Por eso el `Engine` evita repetirlo:

- **Layout.** El árbol de Taffy, con los párrafos ya maquetados, vive entre frames
  (`LayoutCache`) y se reutiliza tal cual mientras no cambie nada de lo que lo determina: el árbol
  de nodos (si la fase de estilo encuentra un cambio que lo afecte), el tamaño de la ventana y el
  texto que muestran los campos (una huella de todos, porque se puede escribir o componer con el
  IME sin pasar por Python). Hover, scroll, animaciones y parpadeo solo repintan.
- **Diff por key.** Si algo cambió, el árbol de Taffy no se rehace: `Engine::reconcile` recorre
  el árbol nuevo y cada nodo reutiliza el nodo de Taffy que tenía su key en el layout anterior.
  Solo lo marca sucio si cambia lo que afecta al layout: su estilo de Taffy (que es exactamente lo
  que el layout ve, así que colores, sombras u opacidad no cuentan), su contenido (el
  `ParagraphKey` de un texto, el tamaño natural de una imagen) o la lista de hijos. Taffy propaga
  la marca a los ancestros y conserva su caché en todo lo demás: cambiar el fondo de una fila no
  rehace el layout, y cambiar su texto solo recalcula esa rama. Los nodos con keys que ya no
  existen se eliminan. Los hijos se asignan siempre con `set_children`, que desengancha a un nodo
  reutilizado de su padre anterior si cambió de sitio.
- **Párrafos.** El párrafo de un texto que no cambió sigue en su nodo. El de uno que cambia va a
  una reserva indexada por `ParagraphKey` (texto, fuente, tamaño, color, interlineado…) de la que
  otro nodo de este mismo layout puede tomarlo, por **contenido** y no por key: al reordenar textos
  no se repite el shaping. Lo que queda en la reserva tras el layout se descarta.
- **Mediciones.** Taffy mide cada hoja varias veces por layout (mínimo, máximo, definitivo…) y
  cada medición maqueta el párrafo. Cada `TextCtx` memoriza sus mediciones (restricciones →
  tamaño y baseline) y recuerda con qué ancho está maquetado, así que `finalize_text` solo lo
  vuelve a maquetar si el ancho final cambió.

`Pilot.stats` y la suite de `benchmarks/` miden cada fase.

### Invalidación por fases

Cada frame recorre cuatro fases, y cada cambio entra en la primera que le afecta: las anteriores
no se repiten. Como en un navegador, lo caro es rehacer de más.

| Fase | Qué hace | La provoca |
|---|---|---|
| **Estilo** (`Engine::restyle`) | Compara el árbol nuevo con el anterior, nodo a nodo. | Una reconstrucción de la vista. |
| **Layout** (`Engine::update`) | Taffy, párrafos y geometría: regiones, capas y tinta. | Un cambio de estructura o de estilo de layout, el tamaño de la ventana, el texto de un campo. |
| **Composición** (`Engine::update`) | Coloca cada capa según su desplazamiento. | Desplazar un `scroll`. |
| **Pintura** (`Engine::paint`) | Repinta solo la zona dañada. | Colores, transiciones, cursor, tooltip, capas que se movieron. |

- **Estilo.** `restyle` recorre a la vez el árbol anterior, el nuevo y el de layout. Si todos los
  nodos coinciden en lo que determina la geometría (keys, estructura, estilo de Taffy, texto y
  métricas de fuente, manejadores, capas, `capture`, `focusable`, sombra, `press_scale`…), el
  layout, las regiones y la tinta siguen valiendo: solo se apuntan para repintar los nodos cuyo
  estilo cambió. Un texto que solo cambia de color se vuelve a "shapear" en su propio nodo de
  Taffy, con el mismo ancho y las mismas mediciones. Cualquier otro cambio rehace el layout (que
  aun así es incremental, por key), y la comparación sigue hasta el final para anotar qué nodos
  cambiaron de aspecto (`repainted_nodes`: tipo, estilo, texto o propiedades de texto, emparejando
  los hijos por key). En la lista de 10 000 filas, cambiar la selección ya no rehace el layout
  (~57 ms): la comparación cuesta ~12 ms.
- **Capas y regiones.** Tras un layout, `Engine::geometry` registra las regiones de hit-testing y
  las **capas**: la raíz, el contenido de cada `scroll` y cada capa superior (`overlay`, que se
  desplaza con sus ancestros pero escapa de su recorte). Las regiones guardan su rectángulo en
  coordenadas locales de su capa, las que tendrían con todos los `scroll` en el origen. La
  composición (`place_layers`) calcula el desplazamiento acumulado y el recorte de cada capa,
  fija los límites de cada `ScrollState` y, si alguna se movió, recoloca las regiones: desplazar
  no rehace el layout ni recalcula las regiones.
- **Tinta.** Cada nodo de layout guarda la **tinta** de su subárbol: hasta dónde puede pintar,
  contando la sombra (3 sigmas de difuminado), el anillo de foco, el texto que desborda su caja y
  `press_scale`. Los hijos de un `scroll` no cuentan (los recorta su caja) y las capas superiores
  tampoco (se pintan aparte). Aparte, cada nodo guarda su tinta **propia**, la que pinta él sin
  sus hijos; la de los descendientes de un nodo con `press_scale > 1` es la del subárbol escalado,
  porque al pulsarlo se escalan con él. Un subárbol es *sticky* si contiene una capa superior (hay que
  recorrerlo para encolarla) o un campo de texto (su geometría se recalcula al pintarlo).
- **Layout parcial.** Tras un layout, `geometry` devuelve las regiones y capas anteriores (las
  capas que siguen existiendo, por identidad: la raíz, `scroll:<key>` u `overlay:<key>`,
  conservan lo que se pintó de ellas) y `relayout_damage` las compara por key con las nuevas. Un
  nodo daña su tinta propia, antes y después, si cambia su rectángulo, su tinta, su capa, su zona
  visible o su aspecto; si cambia de padre o de hermano anterior (puede quedar por encima o por
  debajo de otro), daña la tinta de todo su subárbol. Los nodos nuevos y los que desaparecen dañan
  su tinta propia: un hijo que cambia lo cubre su propia región, no la de su padre. La barra de un
  `scroll` cuyo contenido cambió de tamaño la repinta la composición (lo que se puede desplazar
  forma parte de lo pintado de la capa). Se repinta la ventana entera si cambió su tamaño o la
  escala, si no se sabe qué nodos cambiaron de aspecto (primer frame, una imagen que cambió en
  disco), si cambió más de la mitad de los nodos (comparar ya no compensa) o si hay keys
  repetidas. Escribir en el formulario de 500 filas pasa de pintar ~0,42 ms a ~0,16 ms, a cambio
  de ~0,35 ms en la fase de estilo y ~0,15 ms de comparar regiones (en el banco de pruebas, con un
  lienzo de 960 × 640 a escala 1: con más píxeles, pintar entero cuesta proporcionalmente más).
- **Daño.** La zona a repintar es la unión de: las capas que se movieron (su zona visible), lo
  que dañó un layout parcial, los nodos que cambiaron en la fase de estilo y aquellos cuya transición avanzó en `tick` (su tinta,
  recortada a lo visible), los campos de texto cuyo aspecto cambió (una huella de cursor,
  selección, composición, parpadeo y foco), el tooltip (su burbuja antes y después) y lo que el
  lienzo no tenga del frame anterior. Si no hay nada, el frame no pinta: un frame ocioso cuesta
  lo que comparar unas huellas. Si la zona dañada pasa del 70 % de la ventana
  (`FULL_PAINT_RATIO`), se pinta entera: sale más barato que la superficie aparte y la copia.
- **Pintura parcial.** El `Painter` se salta los subárboles no *sticky* cuya tinta no toca la zona
  dañada. Skia recorta las aristas de una figura al borde del recorte y su antialiasing cerca del
  corte sale algo distinto del de la figura entera, así que recortar justo a la zona dañada
  dejaría bordes que no casan con lo de alrededor. Por eso la zona se pinta con un margen
  (`CLIP_MARGIN`) en una superficie aparte y se copia solo la zona dañada, alineada a píxeles
  físicos. `tests/test_phases.py` comprueba que cada frame incremental coincide con un repintado
  completo.
- **Lienzo retenido.** Pintar solo una parte exige que el lienzo conserve el frame anterior. El
  piloto reutiliza su superficie; la GPU, su lienzo persistente; la CPU, la edad del buffer de
  softbuffer (`age`: hace cuántos frames se pintó lo que contiene) y el `Runtime` recuerda la zona
  pintada de los últimos frames para ponerlo al día. Con edad 0 (buffer nuevo, o macOS, que no conserva el buffer) se
  repinta entero. Al presentar, `present_with_damage` solo copia a la pantalla la zona pintada.
- **Un solo pintado por frame.** `Runtime::draw_frame` hace layout y composición, avisa a los
  `on_scroll` (que ya conocen el desplazamiento y los límites) y, si alguno invalida la vista,
  reconstruye y vuelve a hacer layout antes de pintar, una sola vez.

### Animaciones en Rust

Las transiciones de hover y pressed se interpolan en el núcleo con suavizado exponencial
(`τ = 70 ms`) usando el `dt` real entre frames. Python solo declara los estados de destino
(`bg_hover`, `bg_pressed`, `press_scale`). Así una animación nunca compite con tu código Python
por el GIL ni depende de su velocidad.

Las **animaciones declarativas** (`transition`, `animate_layout`, `enter`, `exit`) siguen la misma
idea. `motion.rs` tiene las curvas (muelle analítico o easing de CSS) y las pistas (`Track`: un
valor de cuatro componentes que va de un origen a un destino y que, al cambiar de destino, parte
del valor actual). El `Engine` guarda un `Motion` por key y las pone en marcha en dos momentos:

- **Al reconstruir** (`restyle` → `animate_changes`): compara el estilo anterior y el nuevo de los
  nodos con `transition`, y de cada nodo con `exit` que desaparece graba una **instantánea**
  (`Picture`, con el layout anterior, que aún es el vigente) que se pinta encima de su capa
  mientras dura la salida (`Ghost`). No toca el layout: los demás ocupan su hueco enseguida.
- **Tras un layout** (`update` → `start_motions`): compara las regiones nuevas con las anteriores.
  Un nodo con `animate_layout` cuya caja local cambió se pinta desplazado desde la caja que
  mostraba (sus hijos se trasladan con él; un hijo animado solo añade la diferencia), y uno que
  aparece con `enter` arranca desde su efecto.

Los nodos transformados no pueden descartarse por su tinta (que es la de su caja final): ellos y
sus ancestros van en `moving` y dentro de ellos el pintor no recorta; `motion_damage` repinta en
cada frame la zona donde se pintaron y donde se pintan. El hit-testing usa siempre la caja final.

### Hit-testing con burbujeo y barreras

Tras cada layout se registra una `HitRegion` por nodo (rectángulo e índice del padre), en orden
de pintura; la composición la mantiene en su posición absoluta. Para resolver un clic:

1. Se toma la **última** región que contiene el punto (la pintada más arriba).
2. Se sube por los padres hasta encontrar un nodo con `on_click`, o hasta un nodo con
   `capture=True`, que corta la búsqueda.

Esto permite que un clic sobre el texto de un botón llegue al botón, y que un clic dentro de un
modal no llegue al fondo que lo cierra.

### Herencia de estilos de texto

Como en CSS, `color`, `font_size`, `font_weight`, `font_family`, `line_height` y `letter_spacing`
se heredan del contenedor más cercano que los define. La herencia se resuelve una sola vez en
`spec::parse`, no en cada pintura.

## Hilos y el GIL

`aurora._core.run` libera el GIL (`py.detach`) durante todo el bucle de eventos y solo lo toma
para reconstruir la vista o ejecutar un callback. Esto permite que otros hilos de Python trabajen
mientras la ventana está abierta.

Cuando un `Signal` cambia, llama a `_core.wake()`, que se puede invocar desde cualquier hilo:
activa una marca atómica (la vista está desactualizada) y envía un evento propio al bucle de winit
a través de un `EventLoopProxy`. El bucle pide un frame y `Runtime::sync` consume la marca y
reconstruye. `App.spawn()` usa esto para las corrutinas: corren en un bucle `asyncio` en un hilo
aparte y cada `set` despierta la ventana.

## Runtime, ventana y piloto

El estado de una app en marcha —árbol, regiones de hit-testing, puntero, despacho de eventos—
vive en `Runtime` (`src/runtime/`), que no sabe nada de ventanas. Hay dos "conductores":

- `window.rs` traduce los eventos de winit a llamadas al `Runtime` y presenta el frame en el
  framebuffer.
- `pilot.rs` (`Pilot`, expuesto como `app.pilot()`) simula el puntero y pinta en una superficie
  en memoria. Como comparte el `Runtime`, un test de interacción ejercita exactamente la misma
  lógica que la ventana.

Los manejadores se guardan por nombre (`handlers: {"click": fn}`) y se despachan con
`Runtime::dispatch(key, evento, arg)`: añadir un evento nuevo no requiere tocar el bucle.

## Scroll

Un nodo con `scroll` se maqueta con `overflow: hidden` en Taffy (tamaño mínimo automático 0, sin
reservar hueco para la barra) y sus hijos no se encogen en el eje desplazado. Taffy calcula
`scroll_width()`/`scroll_height()`, el desplazamiento máximo.

El estado (`ScrollState` en `src/scroll.rs`: desplazamiento, destino del suavizado, visibilidad de
la barra, arrastre) vive en el `Engine` por key, como las animaciones de hover. Cada `scroll` abre
una capa: tras el layout se registran sus límites (desplazamiento máximo y zona visible) y los
`scroll` que ya no existen se olvidan; en cada frame la composición fija esos límites en su
`ScrollState` (que ajusta el desplazamiento si el contenido encogió) y coloca la capa. Al pintar,
el `Painter` recorta a la caja de relleno y traslada a los hijos. Cada `HitRegion` lleva su `clip`
(la intersección de los `scroll` que la contienen), así que lo que está fuera de la zona visible no
recibe eventos.

La rueda se resuelve con las regiones del último frame: desde la región bajo el puntero se sube
por los ancestros hasta el primer `scroll` que todavía pueda moverse en esa dirección.

### `on_scroll` y listas virtuales

Tras la composición, `Runtime::notify_scroll` compara el desplazamiento y la zona visible de cada
`scroll` con `on_scroll` (las keys se recogen al reconstruir) con lo último que se le avisó, y solo
llama si cambió. No marca la vista como sucia: se llama en cada frame de desplazamiento, y quien
necesite reconstruir cambia un `Signal`. `Runtime::draw_frame` (lo usan la ventana y el piloto)
aprovecha eso: si tras avisar la vista quedó invalidada, reconstruye antes de pintar, así que el
frame se pinta una sola vez y ya con las filas nuevas.

`virtual_list` (Python) se apoya en ello: con filas de alto fijo, el contenido es una caja con el
alto total y las filas visibles colocadas con `position="absolute"`. Su `on_scroll` guarda la zona
visible en un `Signal` solo cuando cambia el rango de filas, así que desplazarse dentro del rango
no toca Python. Con 100 000 filas, una reconstrucción cuesta menos de 1 ms.

Taffy 0.15 maqueta un contenedor sin hijos como una hoja y entonces no vacía su lista de hijos
`absolute` ("hoisted"). Si una lista virtual se queda sin filas, el siguiente layout recorrería
nodos ya borrados. Por eso `Engine::reconcile` sustituye por un nodo nuevo cualquier nodo que pasa
de tener hijos a no tenerlos.

## Imágenes

Un nodo `image` (`Kind::Image`) es una hoja cuyo contexto de layout es su tamaño natural
(`Leaf::Image`): se mide conservando la proporción. Antes de maquetar, `Engine::load_images`
resuelve cada `src` contra una `ImageCache` (`src/image.rs`) indexada por ruta + fecha + tamaño
del archivo (o por un hash de los bytes): cada imagen se decodifica una vez, con mipmaps para
reducir sin aliasing. Los SVG se cargan como `svg::Dom` de Skia y se pintan como vectores. Los
errores de carga se convierten en `FileNotFoundError`/`ValueError` al reconstruir la vista.

## Canvas

Un nodo `canvas` (`Kind::Canvas`) es una caja normal para el layout. Su `Node::draw` es un
`Drawing` de Python (`canvas.py`): la función del usuario ya ligada al tema. No se llama al
construir la vista, porque entonces aún no se conoce el tamaño de la caja: `Runtime::draw_frame`
la llama tras el layout y antes de pintar, como `on_scroll`, a través de `canvas::Canvases`.

- `Drawing(width, height, force)` ejecuta la función sobre un `Canvas` que solo acumula comandos
  (tuplas, con los pinceles deduplicados y los puntos en `bytes` de `f32`) y devuelve el lote.
  `canvas::record` lo recorre una vez y lo graba en un `Picture` de Skia que `Engine` guarda por
  key. `Painter` lo dibuja recortado a la caja de contenido; hover, scroll o animaciones de otros
  nodos lo repintan sin volver a Python.
- `Canvases` decide cuándo llamar: tras una reconstrucción (a todos) o tras un layout (a los que
  cambiaron de tamaño). `force` es `True` si cambió el tamaño o la función (otro `Drawing`, es
  decir, el nodo se volvió a serializar). Con `force=False` —el dict memorizado de un
  `@component`— Python devuelve `None` si no cambió ningún `Signal` que leyera la función en su
  última llamada: se conserva el dibujo.
- Grabar un dibujo nuevo marca el nodo como cambiado de aspecto (`restyled`): solo se repinta su
  zona. El dibujo no afecta a la geometría (`same_geometry` trata el canvas como una caja), así
  que nunca obliga a rehacer el layout.

## Gráficos

Un nodo `chart` (`Kind::Chart`, `src/chart/`) guarda sus series como vistas sin copia de los
búferes de Python (`chart::Column`): el núcleo lee su memoria con el GIL tomado, en el momento de
grabar. El dibujo completo (ejes, rejilla, leyenda y series) se graba en un `Picture` que se
repinta sin volver a Python, como el de un `canvas`; `Charts` decide cuándo volver a grabar: si el
`Chart` es otro objeto (la vista se reconstruyó con datos u opciones nuevas), si cambió la caja o
si cambió su ventana visible.

- **Reducción (LTTB):** cada serie se reduce a ~2 puntos por píxel (*Largest-Triangle-Three-Buckets*
  en Rust), tramo a tramo: los `NaN` cortan la línea y cada tramo recibe el presupuesto que le toca
  por su ancho en pantalla, así un pico vertical no se come los puntos de un tramo ancho. Con x
  ordenada, la ventana se acota con búsqueda binaria y solo se recorren los índices visibles (más
  un punto de margen a cada lado, para que el segmento que cruza el borde se dibuje); con x
  desordenada se filtra punto a punto. Un millón de puntos se graba en milisegundos.
- **Zoom y pan:** con `zoom=True`, `Charts` guarda por key el eje x que grabó (el rectángulo del
  área de dibujo), el dominio de los datos y la ventana visible. La rueda acerca con el puntero
  como ancla, el arrastre y la rueda horizontal desplazan la ventana y el doble clic la devuelve al
  dominio completo; los tres son eventos que mutan la ventana y marcan el gráfico como *sucio*
  (`dirty`), así que el siguiente frame lo vuelve a grabar y repinta solo su zona. La ventana vive
  fuera del `Chart` (que es inmutable y puede compartirse entre frames) y sobrevive a las
  reconstrucciones; se recorta al dominio al grabar, así que unos datos nuevos no la dejan fuera.
- Sin zoom, el eje y sale del dominio completo; con zoom, de los puntos visibles (`y_min`/`y_max`
  lo fijan). El gráfico no toca Python para nada de esto: la interacción entera vive en `Runtime`
  y `Charts`.

## Campos de texto

Un `text_input` es un nodo `input` (`Kind::Input`): una hoja con párrafo, como `text`, cuyo valor
llega de Python en cada reconstrucción. La edición vive en Rust, en un `InputState` por key en el
`Engine` (`src/input.rs`): un `Editor` puro (`src/edit.rs`: texto, cursor, selección y deshacer,
con posiciones en bytes UTF-8 alineadas a grafemas), la composición del IME, el parpadeo y el
desplazamiento horizontal.

Cada tecla que el editor atiende modifica el `Editor` y llama a `on_change(texto)`; el Signal se
actualiza y la vista se reconstruye. Al reconstruir, `Engine::sync_inputs` compara el valor que
llega de Python con el del editor: si difieren, Python manda (`set_external`), lo que permite vaciar
un campo al enviar o rechazar un cambio.

Skia mide las posiciones en UTF-16: `input.rs` convierte en ambos sentidos para colocar el cursor
(`get_line_metrics_at` y `get_rects_for_range`), pintar la selección y resolver un clic
(`get_glyph_position_at_coordinate`). Tras pintar, cada campo guarda una copia de su párrafo y su
origen para resolver clics y flechas verticales hasta el siguiente frame. El parpadeo no anima a
60 fps: la ventana programa un despertar (`ControlFlow::WaitUntil`) para el próximo cambio.

## Teclado y foco

El foco es estado del `Engine` (`focused` y `focus_visible`), igual que el hover. El orden de Tab
es el de las `HitRegion` enfocables del último frame; si hay una región `capture`, solo cuentan sus
descendientes. Una tecla se entrega como `KeyEvent` (`src/keys.rs`) a los `on_key` subiendo desde
la región enfocada por sus padres; si ninguno devuelve un valor verdadero, el `Runtime` aplica el
comportamiento por defecto (foco, activación, desplazamiento). El anillo se anima con el mismo
suavizado que hover y pressed y se pinta después de los hijos.

## Tooltips

El tooltip es lo único de los componentes nuevos que vive en el núcleo, porque depende del hover y
del tiempo. Al recalcular el hover, el `Runtime` busca el primer ancestro con `tooltip` bajo el
puntero (`Tip` en el `Engine`); el reloj real (`advance_clock`) acumula tiempo y, pasado el
retardo, la burbuja aparece con el mismo suavizado que el hover. La ventana duerme hasta ese
momento con `next_wakeup`, como con el parpadeo del cursor. Se pinta al final del frame, encima de
las capas, y no registra `HitRegion`: no intercepta el ratón.

## Capas

Un nodo con `layer="overlay"` se maqueta en su sitio, pero el `Painter` lo aplaza: lo encola y lo
pinta al terminar el árbol, en coordenadas absolutas. Como sus `HitRegion` se registran después,
también gana el hit-testing; su índice de padre sigue apuntando a su padre en el árbol, así que el
burbujeo no cambia. Cada capa superior es también una capa de composición: se desplaza con los
`scroll` que la contienen, pero no la recortan.

## Extender Aurora

- **Un componente nuevo** casi nunca necesita Rust: se compone con primitivas en la familia que le
  corresponda dentro de `components/`. Si se puede hacer así, hazlo así.
- **Una propiedad de estilo nueva** toca tres lugares: el campo en `spec::Style` y su parseo,
  su efecto en `taffy_style` (layout) o en `Painter::paint` (pintura), y su documentación en
  [`reference.md`](reference.md). Si hace que el nodo pinte fuera de su caja (como una sombra) o
  cambia las regiones de hit-testing, también va en `compute_ink` y en `same_geometry` (fase de
  estilo); si no, cambiarla ya solo repinta el nodo.
- **Un nuevo tipo de nodo** (imagen, canvas, input) añade una variante a `spec::Kind`, su
  medición en el layout y su pintura.

Cualquier cambio visual debería venir con un test que lo renderice (`tests/test_render.py`).
