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
