# Roadmap

Plan orientativo hacia la 1.0. Las versiones se ordenan por **valor para quien construye apps**,
no por facilidad de implementación. Cada hito termina con algo que se puede usar.

Leyenda: ✅ hecho · 🚧 en curso · ⏳ planificado

---

## v0.1 — Fundamentos ✅

*La tesis funciona: Python describe, Rust pinta, y el resultado se ve profesional.*

- ✅ Puente PyO3 + maturin, wheel abi3 (Python ≥ 3.11), integración con uv
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

## v0.3 — Rendimiento ✅

*Escalar a miles de elementos manteniendo 60 fps.*

- ✅ **Reactividad de grano fino**: `@component` registra los `Signal` que lee y solo se reconstruye si cambian ellos o sus argumentos
- ✅ Caché de layout y de párrafos entre frames (con mediciones de texto memorizadas)
- ✅ Diff del árbol por `key`: el layout de las ramas que no cambian se reutiliza al reconstruir
- ✅ Invalidación por fases (estilo → layout → pintura → composición): solo se repinta la zona que cambió
- ✅ **Backend GPU** de Skia (Vulkan en Windows y Linux, Metal en macOS) detrás de un trait `Surface`, con la CPU de respaldo
- ✅ Listas virtualizadas (`virtual_list`, filas de alto fijo) y evento `on_scroll`
- ✅ Suite de benchmarks reproducible en CI (lista de 10k ítems, dashboard de 50 paneles, escritura)

## v0.4 — Datos y gráficos ✅

*Dashboards de nivel profesional sin librerías externas.*

- ✅ `canvas`: API de dibujo inmediato desde Python, enviada en lote a Rust
- ✅ Charts nativos (líneas, barras, áreas, dispersión) alimentados con numpy/polars sin copias
- ✅ Downsampling (LTTB) en Rust para millones de puntos, zoom y pan
- ✅ `table` con ordenación, columnas redimensionables y virtualización

## v0.5 — Experiencia de desarrollo ✅

- ✅ **Hot reload** que conserva el estado de los `Signal` (`aurora dev app.py`)
- ✅ Inspector visual del árbol y profiler de frames
- ✅ Animaciones declarativas (`animate.spring()`, transiciones de entrada/salida y de layout)
- ✅ `aurora build`: empaquetado a ejecutable con un comando
- ✅ Documentación publicada con ejemplos vivos

## v0.6 — Escritorio y estabilidad ✅

*Una app de Aurora se comporta como una app del sistema, y su API tiene reglas.*

- ✅ Accesibilidad completa con AccessKit (lectores de pantalla, navegación por teclado)
- ✅ Integración con el escritorio:
  - ✅ Multi-ventana (`app.window(...)`, ciclo de vida y cierre por ventana)
  - ✅ Diálogos nativos (abrir/guardar archivo)
  - ✅ Bandeja del sistema
  - ✅ Menús nativos (barra de la app y contextuales)
  - ✅ Notificaciones del sistema (`app.notify`, con callback de clic)
  - ✅ Soltar archivos desde el explorador (`on_drop`, `on_drop_hover`)
- ✅ Política de estabilidad de la API: qué es público, plazos de obsolescencia y avisos (`AuroraDeprecationWarning`)
- ✅ Componentes de entrada: `number_input`, `combobox` y `date_picker`
- ✅ Wheels precompiladas en PyPI para Windows, macOS (x86_64/arm64) y Linux

## v0.7 — Ventanas y arrastre ⏳

*Lo que toda app de escritorio acaba pidiendo y hoy obliga a rodeos.*

- ✅ **Opciones de ventana**: tamaño mínimo y máximo, posición, maximizada y pantalla completa,
  siempre encima, y recordar tamaño y posición entre sesiones (`App(..., remember="mi-app")`)
- ⏳ Ventanas **sin marco** con barra de título propia (zonas de arrastre y botones del sistema)
- ⏳ **Arrastrar y soltar dentro de la app**: reordenar listas y mover elementos entre
  contenedores (kanban), con vista previa, accesible por teclado y simulable con `Pilot`
- ⏳ `virtual_list` con filas de **alto variable** (chats, registros, feeds)

## v0.8 — Componentes para apps complejas ⏳

*Herramientas internas grandes sin construir los widgets a mano.*

- ⏳ `tree`: árbol expandible con selección, teclado y virtualización
- ✅ `splitter`: paneles redimensionables
- ✅ `popover`: contenido flotante anclado a un elemento
- ⏳ Selectores de hora y de color
- ⏳ Texto enriquecido: tramos con estilos dentro de un párrafo y render de Markdown

## v0.9 — Reconstruir menos ⏳

*Que el coste de un cambio dependa de lo que cambia, no del tamaño de la vista.*

- ⏳ Reconstrucción parcial: un `Signal` que cambia vuelve a ejecutar solo las partes de la vista
  que lo leen, también fuera de `@component`
- ⏳ Tiempo de arranque medido en los benchmarks y con objetivo

## 1.0 — Criterios de salida 🎯

La 1.0 sale cuando se cumplen todos, no en una fecha:

- La API pública está congelada: nada pendiente de obsolescencia, y desde aquí la
  [política de estabilidad](https://yoshilol0526.github.io/aurora/stability/) solo permite romper en versiones mayores
- Cada componente se ve bien por defecto, anuncia su rol a los lectores de pantalla, se maneja
  con teclado y tiene tests de render y de interacción
- La documentación cubre toda la API, con guía, referencia y recetas para las tareas habituales
- Ninguna limitación grave conocida en Windows, macOS y Linux (X11); las que dependan de terceros
  (menús nativos en Linux, soltar archivos en Wayland) están documentadas
- 60 fps en la suite de benchmarks en el hardware de referencia de la CI

---

¿Quieres impulsar algún punto? Abre un issue con la etiqueta `roadmap` explicando tu caso de uso:
los casos reales son lo que más pesa al priorizar.
