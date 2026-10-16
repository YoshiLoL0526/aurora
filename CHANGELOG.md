# Changelog

Todos los cambios relevantes de Aurora se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[Versionado Semántico](https://semver.org/lang/es/). Mientras la versión sea `0.x`, cualquier
versión menor puede incluir cambios incompatibles, que siempre se señalarán aquí.

## [Sin publicar]

### Añadido

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

### Cambiado

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
