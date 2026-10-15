# Guía: tu primera app con Aurora

En esta guía construimos, paso a paso, un **monitor de servicios**: una lista de servicios con su
estado, filtros, un panel de resumen, un modal de detalle y tema claro/oscuro. Por el camino
aparecen todos los conceptos importantes de Aurora.

Cada paso es un programa completo que puedes ejecutar. Si algo no queda claro, la
[referencia](reference.md) tiene el detalle de cada propiedad.

1. [Instalación](#1-instalación)
2. [Una ventana](#2-una-ventana)
3. [Layout: filas, columnas y espacio](#3-layout-filas-columnas-y-espacio)
4. [Estilo y tokens de tema](#4-estilo-y-tokens-de-tema)
5. [Estado con Signal](#5-estado-con-signal)
6. [Listas y componentes propios](#6-listas-y-componentes-propios)
7. [Filtros y valores derivados](#7-filtros-y-valores-derivados)
8. [Superposiciones: modales y toasts](#8-superposiciones-modales-y-toasts)
9. [Tema claro y oscuro](#9-tema-claro-y-oscuro)
10. [Tests sin pantalla](#10-tests-sin-pantalla)

---

## 1. Instalación

Necesitas Python ≥ 3.10, [uv](https://docs.astral.sh/uv/) y Rust ([rustup](https://rustup.rs)).

```bash
git clone https://github.com/<usuario>/aurora.git
cd aurora
uv sync
```

`uv sync` compila el núcleo nativo e instala Aurora en modo editable dentro de `.venv`. Crea tu
archivo en cualquier carpeta del proyecto y ejecútalo con `uv run mi_app.py`.

## 2. Una ventana

```python
from aurora import App, text


def view():
    return text("Hola, Aurora", size=32, weight=700)


App(view, title="Monitor").run()
```

Tres ideas que se mantienen durante toda la guía:

- **La vista es una función.** `view()` devuelve la descripción de la interfaz. Aurora la vuelve a
  llamar cuando algo puede haber cambiado.
- **El elemento raíz ocupa toda la ventana** y toma el fondo, el color y la fuente del tema.
- **Los tamaños son lógicos.** `size=32` se ve igual de grande en una pantalla normal y en una
  Retina.

## 3. Layout: filas, columnas y espacio

Los hijos se añaden con corchetes. `row` los coloca en horizontal y `column` en vertical:

```python
from aurora import App, column, row, spacer, text


def view():
    return column(padding=32, gap=16)[
        row(align="center")[
            text("Servicios", size=28, weight=700),
            spacer(),  # ocupa todo el espacio libre
            text("3 en línea", color="$muted"),
        ],
        text("Estado de la infraestructura en tiempo real.", color="$muted"),
    ]


App(view, title="Monitor", size=(900, 600)).run()
```

- `padding` es el relleno interior y `gap` la separación entre hijos.
- `align` alinea en el eje cruzado (`"center"` centra verticalmente dentro de una `row`).
- `spacer()` empuja lo que viene detrás hasta el final. Es la forma idiomática de separar
  "izquierda" y "derecha".

## 4. Estilo y tokens de tema

Los colores del tema se usan con tokens que empiezan por `$`. Así la app cambia de aspecto
completo al cambiar de tema, sin tocar la vista.

```python
from aurora import App, box, column, row, text


def service_row(name: str, region: str, online: bool):
    color = "$success" if online else "$danger"
    return row(
        gap=12,
        align="center",
        padding=(14, 16),
        radius="$md",
        bg="$surface",
        border_width=1,
        border_color="$border",
    )[
        box(width=10, height=10, radius="$full", bg=color),
        column(gap=2, grow=1)[
            text(name, weight=600),
            text(region, size=12, color="$muted"),
        ],
        text("En línea" if online else "Caído", size=12, weight=600, color=color),
    ]


def view():
    return column(padding=32, gap=10)[
        service_row("API pública", "us-east-1", True),
        service_row("Workers", "eu-west-1", False),
    ]


App(view, title="Monitor", size=(900, 600)).run()
```

Fíjate en que `service_row` es **una función normal de Python** que devuelve elementos. Así se
crean componentes en Aurora: sin clases, sin registros ni decoradores.

## 5. Estado con Signal

Un `Signal` guarda un valor. Léelo llamándolo (`s()`) y cámbialo con `set` o `update`. Cualquier
elemento con `on_click` se vuelve interactivo, con hover y pulsación animados de serie.

```python
from aurora import App, Signal, button, column, row, text

checks = Signal(0)


def view():
    return column(padding=32, gap=16)[
        text(lambda: f"Comprobaciones realizadas: {checks()}", size=20, weight=600),
        row(gap=8)[
            button("Comprobar ahora", lambda: checks.update(lambda n: n + 1)),
            button("Reiniciar", lambda: checks.set(0), variant="ghost"),
        ],
    ]


App(view, title="Monitor", size=(900, 600)).run()
```

`text(lambda: ...)` recibe una función en lugar de un string: se evalúa en cada actualización,
así el texto siempre refleja el estado actual.

## 6. Listas y componentes propios

Guarda los datos en un `Signal` y genera la lista con una comprensión normal de Python. Usa datos
**inmutables** (tuplas, dataclasses congeladas) y reemplázalos al cambiar: es más fácil de razonar
y evita errores sutiles.

```python
from dataclasses import dataclass, replace

from aurora import App, Signal, box, column, row, text


@dataclass(frozen=True)
class Service:
    name: str
    region: str
    online: bool
    latency_ms: int


services = Signal(
    (
        Service("API pública", "us-east-1", True, 42),
        Service("Workers", "eu-west-1", False, 0),
        Service("Base de datos", "us-east-1", True, 8),
        Service("CDN", "global", True, 15),
    )
)


def toggle(name: str):
    services.update(lambda ss: tuple(replace(s, online=not s.online) if s.name == name else s for s in ss))


def service_row(s: Service):
    color = "$success" if s.online else "$danger"
    return row(
        key=f"svc-{s.name}",  # identidad estable en listas
        gap=12,
        align="center",
        padding=(14, 16),
        radius="$md",
        bg="$surface",
        bg_hover="$surface_hover",
        border_width=1,
        border_color="$border",
        on_click=lambda: toggle(s.name),
    )[
        box(width=10, height=10, radius="$full", bg=color),
        column(gap=2, grow=1)[
            text(s.name, weight=600),
            text(s.region, size=12, color="$muted"),
        ],
        text(f"{s.latency_ms} ms" if s.online else "Caído", size=12, weight=600, color=color),
    ]


def view():
    return column(padding=32, gap=10)[
        text("Haz clic en un servicio para cambiar su estado", color="$muted"),
        [service_row(s) for s in services()],
    ]


App(view, title="Monitor", size=(900, 600)).run()
```

> **¿Por qué `key`?** Aurora conserva el estado visual de cada elemento (la transición de hover,
> por ejemplo) entre actualizaciones. En listas que cambian de orden o de tamaño, `key` le dice
> qué elemento es cuál.

Si la lista puede crecer más que la ventana, envuélvela en `scroll`. Recorta lo que no cabe y se
desplaza con la rueda, el trackpad o arrastrando su barra, que aparece al desplazarse o al acercar
el puntero al borde:

```python
from aurora import scroll


def view():
    return column(padding=32, gap=10)[
        text("Haz clic en un servicio para cambiar su estado", color="$muted"),
        scroll(key="services", gap=10)[[service_row(s) for s in services()]],
    ]
```

Un `scroll` vertical sin `height` ocupa el espacio libre de su contenedor, y sus hijos mantienen
su tamaño en lugar de encogerse para caber. Con una `key`, la posición se conserva aunque la vista
se reconstruya.

## 7. Filtros y valores derivados

Los valores derivados (totales, porcentajes, listas filtradas) **no se guardan**: se calculan
dentro de la vista a partir de los `Signal`. Una sola fuente de verdad, cero sincronización manual.

Añade esto al programa del paso anterior:

```python
from aurora import row, stat

show_down_only = Signal(False)


def summary():
    ss = services()
    up = [s for s in ss if s.online]
    avg = sum(s.latency_ms for s in up) / len(up) if up else 0
    return row(gap=16)[
        stat("EN LÍNEA", f"{len(up)}/{len(ss)}"),
        stat("LATENCIA MEDIA", f"{avg:.0f} ms"),
        stat("CAÍDOS", str(len(ss) - len(up)), positive=False),
    ]


def filter_chip():
    on = show_down_only()
    return row(
        padding=(6, 12),
        radius="$full",
        border_width=1,
        bg="$primary" if on else "$surface",
        border_color="$primary" if on else "$border",
        on_click=lambda: show_down_only.set(not on),
    )[text("Solo caídos", size=12, weight=600, color="#FFFFFF" if on else "$text")]


def view():
    visible = [s for s in services() if not show_down_only() or not s.online]
    return column(padding=32, gap=16)[
        summary(),
        row()[filter_chip()],
        [service_row(s) for s in visible],
        not visible and text("Todo funciona correctamente ✓", color="$success"),
    ]
```

`not visible and text(...)` es un patrón habitual: si la condición es falsa, el valor es `False`
y Aurora lo ignora.

## 8. Superposiciones: modales y toasts

Para dibujar algo **encima** del resto, usa `position="absolute"` con desplazamientos. Un modal
es un fondo semitransparente que cubre todo y, dentro, una tarjeta centrada:

```python
from aurora import box, button, card, row, text

selected = Signal(None)  # nombre del servicio abierto, o None


def detail_modal():
    name = selected()
    if name is None:
        return None
    s = next(s for s in services() if s.name == name)
    return box(
        position="absolute",
        top=0,
        right=0,
        bottom=0,
        left=0,
        bg="#000000AA",
        align="center",
        justify="center",
        on_click=lambda: selected.set(None),  # clic fuera: cerrar
    )[
        card(width=420, capture=True)[  # capture: los clics dentro no cierran
            text(s.name, size=20, weight=700),
            text(f"Región {s.region} · {s.latency_ms} ms", color="$muted"),
            row(gap=8, justify="end")[
                button("Cerrar", lambda: selected.set(None), variant="soft"),
                button("Reiniciar servicio", lambda: (toggle(s.name), selected.set(None))),
            ],
        ]
    ]
```

Coloca el modal como **último hijo de la raíz** para que se pinte por encima de todo (o dale
`layer="overlay"`, que lo pinta encima aunque esté en otro sitio del árbol), y abre el
detalle desde la fila cambiando su `on_click` a `lambda: selected.set(s.name)`:

```python
def view():
    return box()[
        column(padding=32, gap=16)[...],  # tu contenido
        detail_modal(),
    ]
```

`capture=True` es la clave: sin él, un clic dentro de la tarjeta "subiría" hasta el fondo y
cerraría el modal. Un toast es lo mismo sin fondo: un `row` con `position="absolute"`,
`right=24` y `bottom=24`.

## 9. Tema claro y oscuro

Pasa un `Signal[Theme]` a `App` y cámbialo cuando quieras. Como todo usa tokens, la interfaz
completa se actualiza:

```python
from aurora import DAYLIGHT, MIDNIGHT

theme = Signal(MIDNIGHT)


def toggle_theme():
    theme.set(DAYLIGHT if theme() is MIDNIGHT else MIDNIGHT)


App(view, title="Monitor", size=(900, 600), theme=theme).run()
```

Para crear tu propio tema, consulta [Temas y tokens](reference.md#temas-y-tokens).

## 10. Tests sin pantalla

`render_png` dibuja la vista exactamente como en la ventana, pero a un archivo. Sirve para tests
de snapshot, para CI sin pantalla y para generar capturas de documentación:

```python
def test_monitor_renders(tmp_path):
    app = App(view, size=(900, 600))
    app.render_png(str(tmp_path / "monitor.png"))
    assert (tmp_path / "monitor.png").stat().st_size > 0
```

Como la vista es una función de tus `Signal`, puedes preparar cualquier estado (un servicio caído,
el modal abierto, el tema claro) y renderizarlo sin simular ningún clic.

Para probar la **interacción**, `app.pilot()` ejecuta la app sin ventana y simula el puntero, con
el mismo hit-testing que la ventana real:

```python
def test_modal_opens_and_closes():
    pilot = App(view, size=(900, 600)).pilot()
    pilot.click("svc-CDN")  # clic en la fila con key="svc-CDN"
    assert selected() == "CDN"
    pilot.click_at(10, 10)  # clic en el fondo: cierra el modal
    assert selected() is None
```

---

## Siguientes pasos

- Lee el código de [`examples/studio.py`](../examples/studio.py): una app completa con
  navegación, kanban, gráficos y overlays que usa todo lo de esta guía.
- Revisa la [referencia](reference.md) para descubrir todas las propiedades de estilo.
- Si te interesa cómo funciona por dentro, sigue con la [arquitectura](architecture.md).
