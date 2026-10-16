# Roadmap

Plan orientativo hacia la 1.0. Las versiones se ordenan por **valor para quien construye apps**,
no por facilidad de implementación. Cada hito termina con algo que se puede usar.

Leyenda: ✅ hecho · 🚧 en curso · ⏳ planificado

---

## v0.1 — Fundamentos ✅

*La tesis funciona: Python describe, Rust pinta, y el resultado se ve profesional.*

- ✅ Puente PyO3 + maturin, wheel abi3 (Python ≥ 3.10), integración con uv
- ✅ Layout flexbox con Taffy: `gap`, `padding`, alineación, `grow`/`shrink`, `wrap`, `%`, posicionamiento absoluto
- ✅ Render con Skia: esquinas redondeadas, bordes, sombras con blur, gradientes lineales, opacidad
- ✅ Texto con shaping real, herencia de estilos, alineación por baseline, `max_lines` con elipsis
- ✅ Ventana nativa (winit) con el bucle de eventos fuera del GIL
- ✅ Hover y pressed animados en Rust, `press_scale`
- ✅ Clics con burbujeo hasta el ancestro interactivo y barreras de eventos (`capture`) para modales
- ✅ `Signal`, temas con tokens (`MIDNIGHT`, `DAYLIGHT`) y tema reactivo
- ✅ Componentes base: `button` (3 variantes), `card`, `badge`, `stat`
- ✅ Render headless a PNG, tests y workflows de CI (lint, tests en 3 SO, release a PyPI)

## v0.2 — Apps de verdad ✅

*Lo mínimo para construir herramientas que se usen a diario.*

- ✅ **Scroll**: contenedor `scroll` con clipping, rueda suave, trackpad, encadenado y barra arrastrable
- ✅ **Input de texto**: cursor, selección, copiar/pegar, IME, deshacer; `text_input` y `textarea`
- ✅ **Teclado y foco**: navegación con Tab, atajos (`on_key`), anillo de foco visible
- ✅ **Imágenes**: PNG/JPEG/WebP/SVG con `fit` (cover, contain, fill, none) y caché
- ✅ Más componentes: `checkbox`, `switch`, `select`, `tabs`, `tooltip`, `divider`, `avatar`
- ✅ Despertar el bucle cuando un `Signal` cambia desde otro hilo o una corrutina `asyncio` (`app.spawn`)
- ✅ Piloto headless (`app.pilot()`) para tests de interacción y capas (`layer="overlay"`)

## v0.3 — Rendimiento 🚧

*Escalar a miles de elementos manteniendo 60 fps.*

- ✅ **Reactividad de grano fino**: `@component` registra los `Signal` que lee y solo se reconstruye si cambian ellos o sus argumentos
- ✅ Caché de layout y de párrafos entre frames (con mediciones de texto memorizadas)
- ✅ Diff del árbol por `key`: el layout de las ramas que no cambian se reutiliza al reconstruir
- ⏳ Invalidación por fases (estilo → layout → pintura → composición)
- ⏳ **Backend GPU** de Skia (Metal, Direct3D, Vulkan) detrás de un trait `Surface`
- ✅ Listas virtualizadas (`virtual_list`, filas de alto fijo) y evento `on_scroll`
- ✅ Suite de benchmarks reproducible en CI (lista de 10k ítems, dashboard de 50 paneles, escritura)

## v0.4 — Datos y gráficos ⏳

*Dashboards de nivel profesional sin librerías externas.*

- ⏳ `canvas`: API de dibujo inmediato desde Python, enviada en lote a Rust
- ⏳ Charts nativos (líneas, barras, áreas, dispersión) alimentados con numpy/polars sin copias
- ⏳ Downsampling (LTTB) en Rust para millones de puntos, zoom y pan
- ⏳ `table` con ordenación, columnas redimensionables y virtualización

## v0.5 — Experiencia de desarrollo ⏳

- ⏳ **Hot reload** que conserva el estado de los `Signal`
- ⏳ Inspector visual del árbol y profiler de frames
- ⏳ Animaciones declarativas (`animate.spring()`, transiciones de entrada/salida y de layout)
- ⏳ `aurora build`: empaquetado a ejecutable con un comando
- ⏳ Documentación publicada con ejemplos vivos

## Hacia la 1.0 ⏳

- ⏳ Accesibilidad completa con AccessKit (lectores de pantalla, navegación por teclado)
- ⏳ Multi-ventana, diálogos nativos (abrir/guardar archivo), bandeja del sistema, menús
- ⏳ API estable con política de deprecación documentada
- ⏳ Wheels precompiladas en PyPI para Windows, macOS (x86_64/arm64) y Linux

---

¿Quieres impulsar algún punto? Abre un issue con la etiqueta `roadmap` explicando tu caso de uso:
los casos reales son lo que más pesa al priorizar.
