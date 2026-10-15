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
├── components.py    Componentes con estilo (button, card, badge, stat), solo con primitivas
├── signal.py        Estado reactivo
├── theme.py         Design tokens y temas MIDNIGHT / DAYLIGHT
└── _core.pyi        Stubs del módulo nativo

src/                 (crate aurora_core → módulo aurora._core)
├── lib.rs           Funciones expuestas a Python: render_png, run, wake, Pilot
├── spec.rs          Árbol de Python (dicts) → Node tipado; herencia de estilos de texto
├── color.rs         Parseo de colores e interpolación
├── render.rs        Engine: layout (Taffy) + pintura (Skia) + capas + animación + hit-testing
├── runtime.rs       Estado de la app en marcha: árbol, puntero, rueda, despacho de eventos, wake
├── scroll.rs        Estado de los contenedores scroll: desplazamiento, suavizado, barra
├── keys.rs          KeyEvent y parseo de combinaciones ("ctrl+s", "mod+k")
├── edit.rs          Modelo de edición puro: texto, cursor, selección, deshacer, grafemas
├── input.rs         Estado de los campos de texto y geometría de cursor y selección
├── image.rs         Decodificación de imágenes (raster y SVG), caché y encaje (fit)
├── window.rs        Bucle de ventana (winit) sobre Runtime, framebuffer (softbuffer)
└── pilot.rs         Piloto headless sobre Runtime para tests de interacción
```

## Ciclo de vida de un frame

```
           ┌────────────────────────── Python (con el GIL) ──────────────────────────┐
 evento ─► │ callback del usuario ─► Signal.set() ─► view() ─► Element ─► to_spec()   │
           └──────────────────────────────────────────────────────────┬──────────────┘
                                                                      │ dict anidado (1 cruce)
           ┌────────────────────────── Rust (sin el GIL) ─────────────▼──────────────┐
           │ spec::parse    → Node tipado, herencia de text props, keys estables     │
           │ Engine::layout → árbol Taffy + medición de texto con Skia               │
           │ Engine::tick   → avanza transiciones hover/pressed (dt real)            │
           │ Painter        → Skia pinta en el framebuffer y registra HitRegions     │
           │ present        → softbuffer muestra el frame                            │
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
6. **Layout.** Se construye un árbol Taffy paralelo. Los nodos de texto llevan un `Paragraph` de
   Skia ya "shapeado" como contexto: el mismo párrafo se usa para medir y para pintar.
7. **Pintura.** `Painter` recorre el árbol: sombra → fondo → borde → texto → hijos. Skia escribe
   directamente en la memoria del framebuffer.

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

### Framebuffer por CPU (de momento)

winit + softbuffer + Skia raster es la combinación más portable y simple por ahora: no hay
contextos de GPU que crear ni drivers con los que pelear. El formato de píxel de softbuffer
(`0x00RRGGBB`) coincide en little-endian con el N32 (BGRA) de Skia, así que Skia pinta
directamente en el buffer de la ventana, **sin copias**. El backend GPU (v0.3) entra detrás
del mismo punto.

### Árbol completo por actualización (de momento)

Aurora reconstruye la vista entera tras cada evento que cambia estado (también tras cada tecla en
un campo de texto). Es una simplificación deliberada:
el coste real es serializar el árbol en Python, que para apps medianas está muy por debajo de un
frame. El diseño ya prepara la reactividad de grano fino de la v0.3:

- Los nodos tienen **identidad estable** (`key` explícita o ruta en el árbol), que ya hoy se usa
  para conservar el estado de animación entre reconstrucciones.
- `Signal` tiene suscriptores, y es el punto natural para registrar dependencias por rama.

### Cachés entre frames

Pintar es barato; lo caro es el layout, y sobre todo el texto: hacer el shaping de un párrafo y
maquetarlo en Skia. Por eso el `Engine` evita repetirlo:

- **Layout.** El árbol de Taffy, con los párrafos ya maquetados, se guarda entre frames
  (`LayoutCache`) y se reutiliza mientras no cambie nada de lo que lo determina: el árbol de
  nodos (`Runtime::sync` llama a `invalidate_layout` al reconstruir), el tamaño de la ventana y
  el texto que muestran los campos (una huella de todos, porque se puede escribir o componer con
  el IME sin pasar por Python). Hover, scroll, animaciones y parpadeo solo repintan.
- **Párrafos.** Al rehacer el layout, los párrafos del anterior van a una reserva indexada por
  `ParagraphKey` (texto, fuente, tamaño, color, interlineado…) y el nuevo los toma de ahí antes de
  crear uno. Se emparejan por **contenido**, no por key: sobreviven a reordenaciones y a keys de
  ruta. Lo que queda en la reserva tras el layout se descarta.
- **Mediciones.** Taffy mide cada hoja varias veces por layout (mínimo, máximo, definitivo…) y
  cada medición maqueta el párrafo. Cada `TextCtx` memoriza sus mediciones (restricciones →
  tamaño y baseline) y las conserva al reciclarse, así que un texto que no cambió no vuelve a
  maquetarse hasta `finalize_text`.

Lo que todavía se paga al reconstruir es construir y calcular el árbol de Taffy entero; reutilizar
las ramas que no cambian (diff por key) es el siguiente paso. `Pilot.stats` y la suite de
`benchmarks/` miden cada fase.

### Animaciones en Rust

Las transiciones de hover y pressed se interpolan en el núcleo con suavizado exponencial
(`τ = 70 ms`) usando el `dt` real entre frames. Python solo declara los estados de destino
(`bg_hover`, `bg_pressed`, `press_scale`). Así una animación nunca compite con tu código Python
por el GIL ni depende de su velocidad.

### Hit-testing con burbujeo y barreras

Durante la pintura se registra una `HitRegion` por nodo (rectángulo absoluto e índice del padre),
en orden de pintura. Para resolver un clic:

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
vive en `Runtime` (`src/runtime.rs`), que no sabe nada de ventanas. Hay dos "conductores":

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
la barra, arrastre) vive en el `Engine` por key, como las animaciones de hover. Al pintar, el
`Painter` recorta a la caja de relleno, traslada a los hijos y registra los límites medidos; tras el
frame, el `Engine` los guarda, ajusta el desplazamiento si el contenido encogió y olvida los
`scroll` que ya no existen. Cada `HitRegion` lleva su `clip` (la intersección de los `scroll` que la
contienen), así que lo que está fuera de la zona visible no recibe eventos.

La rueda se resuelve con las regiones del último frame: desde la región bajo el puntero se sube
por los ancestros hasta el primer `scroll` que todavía pueda moverse en esa dirección.

## Imágenes

Un nodo `image` (`Kind::Image`) es una hoja cuyo contexto de layout es su tamaño natural
(`Leaf::Image`): se mide conservando la proporción. Antes de maquetar, `Engine::load_images`
resuelve cada `src` contra una `ImageCache` (`src/image.rs`) indexada por ruta + fecha + tamaño
del archivo (o por un hash de los bytes): cada imagen se decodifica una vez, con mipmaps para
reducir sin aliasing. Los SVG se cargan como `svg::Dom` de Skia y se pintan como vectores. Los
errores de carga se convierten en `FileNotFoundError`/`ValueError` al reconstruir la vista.

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
burbujeo no cambia.

## Extender Aurora

- **Un componente nuevo** casi nunca necesita Rust: se compone con primitivas en
  `components.py`. Si se puede hacer así, hazlo así.
- **Una propiedad de estilo nueva** toca tres lugares: el campo en `spec::Style` y su parseo,
  su efecto en `taffy_style` (layout) o en `Painter::paint` (pintura), y su documentación en
  [`reference.md`](reference.md).
- **Un nuevo tipo de nodo** (imagen, canvas, input) añade una variante a `spec::Kind`, su
  medición en el layout y su pintura.

Cualquier cambio visual debería venir con un test que lo renderice (`tests/test_render.py`).
