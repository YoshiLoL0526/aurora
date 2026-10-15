# Changelog

Todos los cambios relevantes de Aurora se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[Versionado Semántico](https://semver.org/lang/es/). Mientras la versión sea `0.x`, cualquier
versión menor puede incluir cambios incompatibles, que siempre se señalarán aquí.

## [Sin publicar]

### Añadido

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

[Sin publicar]: https://github.com/<usuario>/aurora/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/<usuario>/aurora/releases/tag/v0.1.0
