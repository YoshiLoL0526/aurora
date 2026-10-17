<p align="center">
  <img src="https://raw.githubusercontent.com/YoshiLoL0526/aurora/main/docs/assets/banner.png" alt="Aurora — Interfaces de escritorio profesionales en Python" width="100%">
</p>

<p align="center">
  <strong>Interfaces de escritorio profesionales, rápidas y elegantes, escritas solo en Python.</strong><br>
  Declarativas · Reactivas · Núcleo nativo en Rust · Sin WebView
</p>

<p align="center">
  <a href="https://yoshilol0526.github.io/aurora/">Documentación</a> ·
  <a href="#inicio-rápido">Inicio rápido</a> ·
  <a href="docs/guide.md">Guía</a> ·
  <a href="docs/reference.md">Referencia</a> ·
  <a href="docs/architecture.md">Arquitectura</a> ·
  <a href="VISION.md">Visión</a> ·
  <a href="ROADMAP.md">Roadmap</a>
</p>

> [!WARNING]
> **Estado: pre-alfa (v0.4).** La API puede cambiar entre versiones menores.
> Ya sirve para herramientas internas y prototipos; todavía no para producción.
> Consulta las [limitaciones conocidas](#limitaciones-conocidas).

---

## ¿Qué es Aurora?

Aurora es una librería para construir **aplicaciones de escritorio con interfaces de nivel profesional
usando únicamente Python**. Describes la interfaz como una función de tu estado; Aurora se encarga del
resto con un motor nativo escrito en Rust: layout, tipografía, render, animaciones y eventos.

Nace de una frustración concreta: para que una app de escritorio en Python *se vea bien*, hoy lo
habitual es montar React + WebView + un backend HTTP, o aceptar la estética de toolkits de otra época.
Aurora apuesta por un camino distinto: **una sola tecnología (Python), una sola ventana nativa y un
aspecto moderno desde la primera línea**.

```python
from aurora import App, Signal, button, card, row, text

clicks = Signal(0)


def view():
    return card(padding=32, gap=16)[
        text(lambda: f"{clicks()} clicks", size=40, weight=800),
        row(gap=8)[
            button("Restar", lambda: clicks.update(lambda c: c - 1), variant="soft"),
            button("Sumar", lambda: clicks.update(lambda c: c + 1)),
        ],
    ]


App(view, title="Contador").run()
```

<p align="center">
  <img src="https://raw.githubusercontent.com/YoshiLoL0526/aurora/main/docs/studio/1-resumen.png" alt="Aurora Studio, la app de demostración" width="100%">
  <br><sub><code>examples/studio.py</code>: navegación, kanban con búsqueda, gráfico interactivo, formularios, ajustes, modal, toasts y tema claro/oscuro.<br>
  Todas las capturas del repositorio están renderizadas por la propia librería.</sub>
</p>

## Por qué Aurora

| | |
|---|---|
| **🐍 Solo Python** | Sin HTML, CSS, JavaScript, bundlers ni servidor local. Tu lógica llama directo a tu base de datos, a una API o a un modelo de IA desde el handler de un botón. |
| **⚡ Rendimiento nativo** | Layout, render y animaciones corren en Rust (Skia + Taffy), fuera del intérprete y sin el GIL. Python solo interviene cuando cambia tu estado. |
| **✨ Elegante por defecto** | Tipografía con shaping real, sombras suaves, gradientes, esquinas redondeadas y transiciones animadas incluidas. Un `button()` sin configurar ya se ve bien. |
| **🧩 Declarativa y componible** | La jerarquía se lee como markup (`column()[...]`). Los componentes son funciones Python normales: se testean, se importan y se comparten como cualquier código. |
| **🔁 Reactiva** | El estado vive en `Signal`s y la interfaz se mantiene sincronizada sola. |
| **🎨 Temas con tokens** | `bg="$primary"` en lugar de colores sueltos. Cambia de tema claro a oscuro en caliente con un `Signal[Theme]`. |
| **⌨️ Apps de verdad** | Scroll con inercia, teclado y foco con Tab, campos de texto con selección, portapapeles, deshacer e IME, imágenes y SVG, y componentes como `select`, `tabs`, `switch` o `tooltip`. |
| **📊 Gráficos con tus datos** | `chart()` dibuja líneas, áreas, barras y dispersión a partir de arrays de numpy o de polars **sin copiarlos**, con los ejes, la rejilla y la leyenda calculados solos. Millones de puntos (reducidos con LTTB en Rust), con zoom de rueda y pan arrastrando. |
| **🧪 Testeable sin pantalla** | `app.render_png()` renderiza cualquier vista sin abrir ventana, y `app.pilot()` simula clics, teclas y rueda con el mismo motor que la ventana: tests de interacción, CI y documentación visual. |

## Inicio rápido

**Requisitos:** Python ≥ 3.11, [uv](https://docs.astral.sh/uv/) y Rust ([rustup](https://rustup.rs)).
En Linux también `libfontconfig-dev` y `libfreetype-dev`.

```bash
git clone https://github.com/YoshiLoL0526/aurora.git
cd aurora
uv sync                          # compila el núcleo Rust (release) e instala en modo editable
uv run examples/hello.py         # tu primera ventana
uv run examples/studio.py        # la demo completa
```

> La primera compilación descarga binarios precompilados de Skia y tarda unos minutos.
> Después solo se recompila el crate propio, y únicamente cuando cambias código Rust.

¿Prefieres pip? `pip install maturin && maturin develop --release`.

Mientras desarrollas, arranca la app con **hot reload**: al guardar, la ventana se actualiza con
el código nuevo sin perder el estado (ver [hot reload](docs/reference.md#hot-reload)):

```bash
uv run aurora dev examples/hello.py
```

Para repartir tu app, empaquétala en un ejecutable con un comando (requiere el extra
`aurora-ui[build]`; ver [empaquetado](docs/reference.md#empaquetado-aurora-build)):

```bash
uv run aurora build app.py --icon assets/icon.ico --include assets
```

## Un vistazo a la API

```python
from aurora import App, Signal, DAYLIGHT, MIDNIGHT, badge, button, card, column, row, spacer, stat, text

theme = Signal(MIDNIGHT)


def toggle_theme():
    theme.set(DAYLIGHT if theme() is MIDNIGHT else MIDNIGHT)


def header():
    return row(align="center", gap=12)[
        text("Panel", size=26, weight=700),
        badge("beta"),
        spacer(),  # empuja lo siguiente a la derecha
        button("Cambiar tema", toggle_theme, variant="ghost"),
    ]


def view():
    return column(padding=32, gap=24)[
        header(),
        row(gap=16)[
            stat("INGRESOS", "$48.2k", "+12%"),
            stat("PEDIDOS", "1.204", "+3%"),
            stat("DEVOLUCIONES", "2,1%", "+0,4", positive=False),
        ],
        card()[
            text("Últimos movimientos", size=15, weight=600),
            text("Una descripción larga que se corta con elipsis…", max_lines=1, color="$muted"),
        ],
    ]


App(view, title="Mi panel", size=(1100, 720), theme=theme).run()
```

| Concepto | En Aurora |
|---|---|
| Estructura | `column`, `row`, `box`, `spacer`; hijos con `[...]` |
| Contenido | `text` (dinámico con `lambda`), `image` (PNG, JPEG, WebP, SVG), `badge`, `stat`, `avatar`, `divider` |
| Interacción | `button`, u `on_click=` en cualquier contenedor; hover y pressed animados; `tooltip` |
| Entrada | `text_input`, `textarea`, `checkbox`, `switch`, `select`, `tabs`, enlazados a un `Signal` |
| Teclado | Tab y foco visible, Enter/Espacio activan, `on_key` con atajos (`e.matches("mod+s")`) |
| Desplazamiento | `scroll()` con rueda suave, trackpad, barra arrastrable y teclado |
| Layout | flexbox: `gap`, `padding`, `align`, `justify`, `grow`, `wrap`, `%`, `position="absolute"` |
| Estilo | `bg`, `gradient`, `radius`, `border_*`, `shadow`, `opacity`, `press_scale` |
| Estado | `Signal(valor)`: `s()`, `s.set(v)`, `s.update(fn)`; seguro desde hilos y `app.spawn(corrutina)` |
| Tests | `app.render_png()` y `app.pilot()`: `click`, `type`, `press`, `scroll`, `png`… |
| Temas | tokens `"$nombre"`, temas `MIDNIGHT` y `DAYLIGHT`, o el tuyo con `Theme(...)` |

La referencia completa de propiedades está en [`docs/reference.md`](docs/reference.md).

## Cómo funciona

```
 Tu código Python                              Núcleo nativo (Rust)
 ─────────────────                             ───────────────────────────────────────────
 view() ─► árbol de Element ─► to_spec() ──►   spec    dict → nodos tipados, herencia de estilos
     ▲                          (1 cruce)      layout  Taffy (flexbox) + medición de texto Skia
     │                                         paint   Skia: formas, sombras, gradientes, texto
     │                                         anim    hover/pressed, scroll suave, foco, tooltips
     │                                         input   edición de texto, IME, portapapeles
 Signal.set() ◄── callback ◄── evento ◄──────  window  winit + framebuffer; bucle sin el GIL
```

Python **describe**; Rust **ejecuta**. La frontera entre ambos se cruza una vez por actualización,
con un árbol completo, en lugar de miles de llamadas pequeñas. Los detalles están en
[`docs/architecture.md`](docs/architecture.md).

**Stack:** [PyO3](https://pyo3.rs) + [maturin](https://www.maturin.rs) ·
[Skia](https://skia.org) (vía `skia-safe`) · [Taffy](https://github.com/DioxusLabs/taffy) ·
[winit](https://github.com/rust-windowing/winit) · GPU con Vulkan/Metal ([vulkano](https://vulkano.rs)) y
[softbuffer](https://github.com/rust-windowing/softbuffer) como respaldo por CPU.

## ¿Cuándo usar Aurora?

Aurora encaja cuando quieres **una app de escritorio con aspecto moderno, escrita en Python, sin
desarrollo web de por medio**: dashboards, herramientas internas, paneles de control para tus
scripts y modelos, utilidades personales.

Si hoy necesitas un toolkit maduro con cientos de widgets, accesibilidad completa y años en
producción, **Qt (PySide6/PyQt)** es la opción sensata. Si tu interfaz vive en el navegador, una
solución web encaja mejor. Aurora no busca reemplazarlas: busca que construir una interfaz
*bonita y rápida* desde Python sea lo más directo posible. Más contexto en [VISION.md](VISION.md).

## Limitaciones conocidas

Aurora es joven. Esto es lo que **todavía no** hace (todo está en el [roadmap](ROADMAP.md)):

- **Vista completa por evento**: cada cambio vuelve a llamar a `view()`. Las ramas marcadas con
  `@component` que no cambiaron se reutilizan, pero el resto se reconstruye.
- Todavía sin accesibilidad ni multi-ventana.

## Documentación

Publicada en **<https://yoshilol0526.github.io/aurora/>**, con buscador, tema claro/oscuro y
ejemplos vivos: cada captura se genera ejecutando el código que la acompaña.

- [**Guía**](docs/guide.md): de cero a una app completa, paso a paso.
- [**Referencia**](docs/reference.md): todas las primitivas, componentes y propiedades de estilo.
- [**Arquitectura**](docs/architecture.md): cómo funciona el núcleo y por qué está diseñado así.
- [**Visión**](VISION.md) y [**Roadmap**](ROADMAP.md): hacia dónde va el proyecto.
- [**Ejemplos**](examples/): `hello.py` para empezar, `studio.py` como app completa, `canvas.py`,
  `charts.py`, `table.py` y `animate.py` por temas, y `brand.py` (genera el banner de este README).

## Contribuir

Las contribuciones son bienvenidas, desde reportar un bug hasta implementar un widget. Lee
[CONTRIBUTING.md](CONTRIBUTING.md) para preparar el entorno, conocer las convenciones y proponer
cambios. Este proyecto sigue un [Código de conducta](CODE_OF_CONDUCT.md).

## Licencia

[MIT](LICENSE) © Raidel y contribuidores de Aurora.
