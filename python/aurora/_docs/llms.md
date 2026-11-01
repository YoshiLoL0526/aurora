# Aurora para modelos (LLM)

Chuleta compacta de Aurora (`aurora-ui`) para modelos de lenguaje y agentes de programación.
Aurora es reciente y **no está en tus datos de entrenamiento**: no supongas APIs de React, Flet,
Tkinter, Qt ni CSS; usa solo lo que aparece aquí o en la referencia. Con Aurora instalado,
`aurora docs` imprime esta chuleta para la versión instalada, `aurora docs <tema>` una sección de
la referencia (`aurora docs button`, `aurora docs pilot`), `aurora docs --search <texto>` busca
y `aurora docs --full` lo imprime todo. Las firmas, las props y los tokens del final se generan
desde la propia librería.

## Modelo mental

- **La vista es una función del estado.** `view()` devuelve un árbol de `Element` construido con
  primitivas y componentes; `App(view).run()` abre la ventana. Aurora vuelve a llamar a `view()`
  tras cada evento y cada vez que cambia un `Signal` que lee: no hay widgets que mutar ni
  `update()` que llamar. Construye los elementos **dentro** de `view()`.
- **El estado vive en `Signal`.** `s = Signal(0)`; se lee llamándolo (`s()`) y se cambia con
  `s.set(v)` o `s.update(fn)`. `set` es seguro desde cualquier hilo o corrutina (`app.spawn`).
- **Funciones = regiones reactivas.** `text(lambda: f"{n()} clics")`, `bg=lambda: ...` o un hijo
  `lambda: [...]` se reevalúan solos cuando cambia lo que leen, sin rehacer la vista entera.
- **Hijos con corchetes:** `column(gap=8)[text("a"), text("b")]`. Dentro valen elementos, listas
  (se aplanan), strings (se vuelven `text`), `None`/`False` (se ignoran: `cond and elemento`) y
  funciones. Los argumentos de las funciones son estilo, nunca hijos.
- **Estilo como argumentos con nombre** (`bg`, `padding`, `radius`, `gap`…), parecidos a CSS pero
  con nombres propios: la lista completa está abajo. Una prop desconocida lanza `TypeError` con
  una sugerencia.
- **Tokens del tema** como strings `"$nombre"` (`"$surface"`, `"$primary"`, `"$md"`); un token
  que no existe lanza `ThemeTokenError`. Los colores son `"#rgb"`, `"#rrggbb"` o `"#rrggbbaa"`.
- **`key` da identidad.** Conserva el estado visual (hover, foco, scroll, texto de un campo,
  animaciones) entre reconstrucciones y es como los tests encuentran un nodo
  (`pilot.click("guardar")`). En listas, una key estable y única por elemento.
- **`@component`** memoriza una función que devuelve un `Element`: con los mismos argumentos
  (hashables) y sin cambios en los `Signal` que lee, no se reconstruye. Para listas grandes.
- Parámetros: los esenciales son posicionales (`text(contenido)`, `button(label, on_click)`); el
  resto, con nombre. Los manejadores son funciones: `on_click=lambda: guardar()`.

```python
from aurora import App, Signal, button, card, row, text

count = Signal(0)


def view():
    return card(padding=24, gap=12)[
        text(lambda: f"{count()} clics", size=28, weight=700, key="total"),
        row(gap=8)[
            button("Sumar", lambda: count.update(lambda n: n + 1), key="sumar"),
            button("Reiniciar", lambda: count.set(0), variant="soft"),
        ],
    ]


App(view, title="Contador", size=(520, 200)).run()
```

## Patrones habituales

- **Listas:** datos inmutables (tuplas, `@dataclass(frozen=True)`) en un `Signal`, sustituidos al
  cambiar: `todos.update(lambda ts: (*ts, nueva))`. Cada fila con `key=f"todo-{t.id}"`.
- **Formularios:** los controles se enlazan a un `Signal` en los dos sentidos:
  `text_input(nombre, placeholder="Nombre")`, `checkbox(acepto, "Acepto")`,
  `select(pais, ["ES", "MX"])`, `slider(volumen)`. Pasa el `Signal`, no su valor.
- **Condicionales:** `cargando() and spinner()`, o `dialog(abierto, contenido, title="…")`,
  que no pinta nada mientras `abierto()` es falso.
- **Layout:** `row`/`column` (flexbox: `gap`, `align`, `justify`, `grow`), `spacer()` empuja lo
  siguiente al final, `scroll()` para lo que no cabe, `virtual_list` para miles de filas.
  `grow=1, width=0` en cada hijo de una `row` reparte el ancho a partes iguales.
- **Trabajo lento:** nunca en el manejador (congela la ventana). Usa `app.spawn(corrutina)` o un
  hilo, y publica el resultado con `Signal.set`.
- **Teclado:** `on_key=fn` recibe un `KeyEvent`; `e.matches("mod+s")` y devuelve `True` si la
  atendió. En la raíz de la vista sirve para atajos globales.

## Errores frecuentes de los modelos

| Mal | Bien | Por qué |
|---|---|---|
| `column(text("a"), text("b"))` | `column()[text("a"), text("b")]` | Los hijos van entre corchetes. |
| `box(background="#fff", margin=8)` | `box(bg="#fff")` dentro de un padre con `gap`/`padding` | Props inventadas: `TypeError`. No hay `margin`. |
| `onClick=f`, `border_radius=8`, `flex=1` | `on_click=f`, `radius=8`, `grow=1` | Nombres de otras librerías. |
| `bg="red"`, `color="primary"` | `bg="#EF4444"`, `color="$primary"` | Solo hex o tokens con `$`. |
| `font_weight="bold"`, `width="100px"` | `weight=700`, `width=100` (o `"50%"`) | Números y porcentajes. |
| `on_click=guardar(x)` | `on_click=lambda: guardar(x)` | Lo primero llama a `guardar` al construir. |
| `items().append(x)` | `items.update(lambda xs: (*xs, x))` | Mutar no avisa, y `set` del mismo objeto es `==`: no hace nada. |
| `text(f"{count}")` | `text(lambda: f"{count()}")` | Un `Signal` se lee llamándolo. |
| `etiqueta = text(f"{n()}")` fuera de `view()` | constrúyelo en `view()` o usa `text(lambda: ...)` | Un elemento creado una vez se queda congelado. |
| `key=str(i)` en una lista que se reordena, o `key=str(random())` | `key=f"tarea-{t.id}"` | Keys estables y únicas. |
| `for t in ts: ... on_click=lambda: borrar(t)` | `lambda t=t: borrar(t)` o una función por fila | Las lambdas en un bucle capturan la variable, no el valor. |
| `App(view())` | `App(view)` | `App` recibe la función. |
| `text_input(nombre(), ...)` | `text_input(nombre, ...)` | Con el valor, el campo no cambia al escribir. |
| `app.run()` en un test | `app.pilot()` / `app.render_png(...)` | `run()` abre una ventana y bloquea. |

## Probar sin ventana

`app.render_png(ruta)` dibuja la vista igual que la ventana, a un archivo. `app.pilot()` ejecuta la
app sin ventana con el mismo runtime y simula el usuario por `key`: `click`, `type`, `press`,
`drag_to`, `wheel`, `focus`, `settle()` (esperar animaciones), `rect(key)`, `a11y_tree()`
(lo que vería un lector de pantalla) y `png(ruta)`. Las excepciones de la vista y de los
manejadores llegan al test.

```python
from aurora import App, Signal, button, column, text, text_input

nombre = Signal("")
saludos = Signal(0)


def view():
    return column(padding=16, gap=8)[
        text_input(nombre, placeholder="Nombre", key="nombre"),
        button("Saludar", lambda: saludos.update(lambda n: n + 1), key="saludar"),
        text(lambda: f"Hola, {nombre()} ({saludos()})", key="saludo"),
    ]


pilot = App(view, size=(320, 200)).pilot()
pilot.click("nombre")
pilot.type("Ada")
pilot.click("saludar")
assert (nombre(), saludos()) == ("Ada", 1)
saludo = next(n for n in pilot.a11y_tree() if n["key"] == "saludo")
assert saludo["value"] == "Hola, Ada (1)"
```

Comprueba tu trabajo así: construye la vista, haz una captura con `render_png` y mírala, y
recorre la interacción con `pilot`. Una prop o un token mal escritos fallan al construir la vista,
con la sugerencia correcta en el mensaje.

## Firmas

`**style` acepta cualquier prop de estilo, de accesibilidad o manejador de la lista siguiente. Toda
prop admite también una función sin argumentos (región reactiva) o `None` (como no pasarla).

### Primitivas

```python
box(**style)
canvas(draw: Callable[[Canvas], Any], **style)
chart(y: Any, *, x: Any = None, kind: Kind = "line", color: str | Sequence[str] | None = None, names: Sequence[Any] | None = None, labels: Sequence[Any] | None = None, y_min: float | None = None, y_max: float | None = None, grid: bool = True, zoom: bool = False, stroke_width: float = 2, point_size: float = 3.5, bar_width: float = 0.7, label_size: float = 11, label_color: str = "$muted", grid_color: str = "$border", **style)
column(**style)
image(src: str | PathLike[str] | bytes, *, fit: Fit = "contain", **style)
markdown(source: str, *, on_link: Callable[[str], Any] | None = None, gap: float = 12, key: str | None = None, **style)
rich_text(*parts: Spans, key: str | None = None, **style)
row(**style)
scroll(*, axis: Literal["x", "y", "both"] = "y", **style)
spacer()
span(content: str, *, weight: int | None = None, color: str | None = None, italic: bool = False, underline: bool = False, strike: bool = False, code: bool = False, size: float | None = None, family: str | None = None, bg: str | None = None, on_click: Callable[[], Any] | None = None)
text(content: TextLike, **style)
```

### Componentes

```python
accordion(sections: Sequence[tuple[Any, str, Element]], open: Signal[Any], *, key: str | None = None, **style)
avatar(name: str = "", *, src: str | PathLike[str] | bytes | None = None, size: float = 32, **style)
badge(label: TextLike, *, tone: str = "accent")
button(label: TextLike, on_click: Callable[[], Any] | None = None, *, variant: Variant = "primary", key: str | None = None, **style)
card(**style)
checkbox(checked: Signal[bool] | bool, label: TextLike | None = None, *, on_change: Callable[[bool], Any] | None = None, key: str | None = None, **style)
color_picker(value: Signal[str], *, palette: Sequence[str] = ..., custom: bool = True, on_change: Callable[[str], Any] | None = None, key: str | None = None, **style)
combobox(value: Signal[Any], options: Options, *, placeholder: str = "Buscar…", empty: str = "Sin resultados", on_change: Callable[[Any], Any] | None = None, key: str | None = None, **style)
date_picker(value: Signal[date | None] | Signal[date], *, min: date | None = None, max: date | None = None, placeholder: str = "Elegir fecha", format: Callable[[date], str] = ..., first_weekday: int = 0, on_change: Callable[[date], Any] | None = None, key: str | None = None, **style)
dialog(open: Signal[bool] | bool, content: Element, *, title: TextLike | None = None, on_close: Callable[[], Any] | None = None, width: float = 420, key: str | None = None, **style)
divider(*, vertical: bool = False, color: str = "$border", **style)
field(control: Element, *, label: str | None = None, hint: str | None = None, error: str | None = None, key: str | None = None, **style)
menu(trigger: Element, items: Sequence[tuple[str, Callable[[], Any]] | tuple[str, Callable[[], Any], dict[str, Any]]], *, key: str, drop: float | None = None, placement: str = "bottom-start", **style)
number_input(value: Signal[float] | Signal[int], *, min: float | None = None, max: float | None = None, step: float = 1, decimals: int | None = None, on_change: Callable[[float], Any] | None = None, key: str | None = None, **style)
pages(current: Signal[Any], views: Mapping[Any, Callable[[], Element]], *, key: str = "pages", **style)
popover(trigger: Element, content: Element, *, open: Signal[bool] | None = None, placement: str = "bottom-start", offset: float = 6, label: str | None = None, on_close: Callable[[], Any] | None = None, key: str | None = None, **style)
progress(value: Signal[float] | float, *, max: float = 1.0, color: str | tuple[str, str, float] = "$primary", **style)
radio(options: Options, selected: Signal[Any], *, key: str | None = None, **style)
segmented(options: Options, selected: Signal[Any], *, width: float = 220, key: str | None = None, **style)
select(value: Signal[Any], options: Options, *, placeholder: str = "Elegir…", key: str | None = None, **style)
skeleton(*, lines: int = 1, width: str | float = "100%", height: float = 14, gap: float = 8, **style)
slider(value: Signal[float], *, min: float = 0.0, max: float = 1.0, width: float = 180, on_change: Callable[[float], Any] | None = None, key: str | None = None, **style)
sortable(items: Sequence[T], item: Callable[[T], Element], *, key: str, group: str | None = None, ident: Callable[[T], Hashable] | None = None, item_label: Callable[[T], TextLike] = str, on_move: Callable[[MoveEvent[T]], Any] | None = None, direction: Literal["column", "row"] = "column", gap: float = 8, empty: Child = None, **style)
spinner(*, size: float = 8, gap: float = 5, tone: str = "$primary", key: str | None = None, **style)
splitter(first: Element, second: Element, *, size: Signal[float] | float = 240, direction: Literal["row", "column"] = "row", min_sizes: tuple[float, float] = (80, 80), step: float = 16, on_change: Callable[[float], Any] | None = None, key: str | None = None, **style)
stat(label: str, value: TextLike, delta: str | None = None, *, positive: bool = True)
switch(on: Signal[bool] | bool, label: TextLike | None = None, *, on_change: Callable[[bool], Any] | None = None, key: str | None = None, **style)
table(rows: Sequence[Any], columns: Sequence[Column | str], *, key: str, sort: Signal[Sort] | None = None, widths: Signal[dict[str, float]] | None = None, on_row_click: Callable[[Any], Any] | None = None, row_height: float = 36, header_height: float = 40, striped: bool = True, empty: str = "Sin datos", overscan: int = 4, **style)
tabs(options: Options, selected: Signal[Any], *, key: str | None = None, **style)
text_input(value: Signal[str] | TextLike, *, placeholder: str = "", on_change: Callable[[str], Any] | None = None, on_submit: Callable[[str], Any] | None = None, key: str | None = None, **style)
textarea(value: Signal[str] | TextLike, *, placeholder: str = "", rows: int = 3, on_change: Callable[[str], Any] | None = None, on_submit: Callable[[str], Any] | None = None, key: str | None = None, **style)
time_picker(value: Signal[time | None] | Signal[time], *, step: int = 15, min: time | None = None, max: time | None = None, hour12: bool = False, placeholder: str = "Elegir hora", format: Callable[[time], str] | None = None, on_change: Callable[[time], Any] | None = None, key: str | None = None, **style)
title_bar(title: TextLike | None = None, *, icon: Element | None = None, actions: Child = None, window: Window | None = None, controls: bool | Literal["windows", "macos"] = True, height: float = 36, key: str = "title-bar", **style)
toast(message: Signal[str | None] | TextLike | None, *, on_close: Callable[[], Any] | None = None, tone: str = "$accent", key: str | None = None, **style)
tooltip(child: Element, tip: str)
tree(roots: Sequence[N], children: Callable[[N], Sequence[N]], *, key: str, label: Callable[[N], TextLike] = str, ident: Callable[[N], Hashable] | None = None, expanded: Signal[set[Any]] | None = None, selected: Signal[Any] | None = None, icon: Callable[[N], Element | None] | None = None, on_select: Callable[[N], Any] | None = None, on_activate: Callable[[N], Any] | None = None, item_height: float = 30, indent: float = 18, overscan: int = 4, **style)
virtual_list(count: int, item: Callable[[int], Element], *, item_height: float | None = None, estimated_height: float = 40, key: str, gap: float = 0, overscan: int = 4, stick_to_end: bool = False, role: str = "list", item_role: str = "listitem", **style)
```

### Utilidades

```python
component(fn: Callable[P, Element])
current_window()
resource(path: str | PathLike[str])
```

### Alias de tipos de las firmas

```python
Child = Union[Element, str, bool, None, Callable[[], "Child"], Iterable["Child"]]
Fit = Literal["contain", "cover", "fill", "none"]
Kind = Literal["line", "area", "bar", "scatter"]
Options = Sequence[T] | Sequence[tuple[T, str]]
Sort = tuple[str, bool] | None
Spans = Span | str | Iterable["Spans"] | None
TextLike = str | Callable[[], Any]
Variant = Literal["primary", "soft", "ghost"]
```

### Clases

```python
App(view: Callable[[], Element], *, title: str = "Aurora", size: tuple[float, float] = (960, 640), resizable: bool = True, min_size: tuple[float, float] | None = None, max_size: tuple[float, float] | None = None, position: tuple[float, float] | None = None, maximized: bool = False, fullscreen: bool = False, always_on_top: bool = False, decorations: bool = True, remember: str | None = None, theme: Theme | Callable[[], Theme] = MIDNIGHT, menu: Sequence[dict[str, Any]] | None = None, app_id: str | None = None, inspector: bool | None = None, reload: bool | None = None, motion: bool | None = None)
    .main
    .notify(title: str, body: str = "", *, icon: str | PathLike[str] | None = None, on_click: Callable[[], Any] | None = None)
    .pilot(*, size: tuple[float, float] | None = None, scale: float = 1.0, inspector: bool = False)
    .quit()
    .register_app_id(name: str | None = None)
    .render_png(path: str, *, size: tuple[float, float] | None = None, scale: float = 2.0)
    .run(*, backend: Literal["auto", "gpu", "cpu"] = "auto", keep_alive: bool | None = None)
    .spawn(coro: Coroutine[Any, Any, T])
    .tray(icon: str | PathLike[str] | bytes, *, tooltip: str | None = None, menu: Sequence[dict[str, Any]] | None = None, on_click: Callable[[str], Any] | None = None, on_double_click: Callable[[str], Any] | None = None, template: bool = False)
    .tray_hide()
    .watch(main: ModuleType | None = None)
    .window(view: Callable[[], Element], *, title: str = "Aurora", size: tuple[float, float] | None = None, resizable: bool = True, min_size: tuple[float, float] | None = None, max_size: tuple[float, float] | None = None, position: tuple[float, float] | None = None, maximized: bool = False, fullscreen: bool = False, always_on_top: bool = False, decorations: bool = True, remember: str | None = None, on_close: Callable[[], Any] | None = None)
    .windows()
Window(app: App, view: Callable[[], Element], *, title: str = "Aurora", size: tuple[float, float] = (960, 640), resizable: bool = True, min_size: tuple[float, float] | None = None, max_size: tuple[float, float] | None = None, position: tuple[float, float] | None = None, maximized: bool = False, fullscreen: bool = False, always_on_top: bool = False, decorations: bool = True, remember: str | None = None, on_close: Callable[[], Any] | None = None, _id: int | None = None)
    .always_on_top
    .close()
    .decorations
    .fullscreen
    .is_open
    .max_size
    .maximized
    .min_size
    .minimize()
    .open()
    .pilot(*, size: tuple[float, float] | None = None, scale: float = 1.0, inspector: bool = False)
    .position
    .render_png(path: str, *, size: tuple[float, float] | None = None, scale: float = 2.0)
    .request_close()
    .resizable
    .size
    .title
Signal(value: T)
    .set(value: T)
    .subscribe(fn: Callable[[T], None])
    .update(fn: Callable[[T], T])
    .value
Pilot(build, width=960.0, height=640.0, scale=1.0, inspector=False, frameless=False)
    .a11y_action(key, action, value=None)
    .a11y_tree()
    .chart_view(key)
    .click(key)
    .click_at(x, y)
    .clipboard
    .cursor
    .drag(key, dx=0.0, dy=0.0, steps=4)
    .drag_to(key, to, steps=8)
    .drop_files(files, key=None, at=None)
    .focus(key)
    .focused
    .frame(dt=Ellipsis)
    .hover_files(files)
    .hovered
    .ime_commit(text)
    .ime_preedit(text)
    .inspection
    .key_down(combo)
    .key_up(combo)
    .leave()
    .mouse_down()
    .mouse_up()
    .move_to(x, y)
    .png(path)
    .press(combo)
    .rect(key)
    .resize(width, height)
    .scroll(key, dy=0.0, dx=0.0)
    .scroll_offset(key)
    .selection(key)
    .settle(max_frames=600)
    .stats
    .tooltip
    .type(text)
    .wheel(dy=0.0, dx=0.0, lines=False)
    .window_requests
Element(kind: str = "box", *, content: TextLike | None = None, key: str | None = None, **props)
    .children
    .content
    .handlers
    .key
    .kind
    .on_click
    .style
    .to_spec(theme: Theme)
Theme(colors: dict[str, str] = <factory>, radius: dict[str, float] = <factory>, font_family: str = "Inter")
    .font_family
    .resolve(value: Any)
```

### Módulos `animate`, `dialogs` y `menus`

```python
animate.effect(*, opacity: float = 1.0, x: float = 0.0, y: float = 0.0, scale: float = 1.0, transition: Transition | None = None)
animate.fade(opacity: float = 0.0, *, transition: Transition | None = None)
animate.pulse(duration: float = 1.0, *, delay: float = 0.0, floor: float = 0.35)
animate.slide(x: float = 0.0, y: float = 0.0, *, fade: bool = True, transition: Transition | None = None)
animate.spring(*, stiffness: float = 380.0, damping: float = 30.0, mass: float = 1.0, delay: float = 0.0)
animate.tween(duration: float = 0.25, *, easing: Easing = "ease_out", delay: float = 0.0)
animate.zoom(scale: float = 0.9, *, fade: bool = True, transition: Transition | None = None)
dialogs.open_file(*, title: str | None = None, directory: str | PathLike[str] | None = None, filters: Filters | None = None)
dialogs.open_files(*, title: str | None = None, directory: str | PathLike[str] | None = None, filters: Filters | None = None)
dialogs.pick_folder(*, title: str | None = None, directory: str | PathLike[str] | None = None)
dialogs.save_file(*, title: str | None = None, directory: str | PathLike[str] | None = None, default_name: str | None = None, filters: Filters | None = None)
menus.bar(*items: dict[str, Any])
menus.item(label: str, on_click: Callable[[], Any], *, shortcut: str | None = None, enabled: bool = True)
menus.predefined(name: str)
menus.separator()
menus.submenu(label: str, *items: dict[str, Any])
```

## Props de estilo

Las de *Texto* se heredan de los contenedores, como en CSS. Detalles y valores por defecto:
`aurora docs style`.

- **Layout**: `direction`: 'row' | 'column', `gap`: float, `padding`: float | (v, h) | (t, r, b, l), `align`: 'start' | 'center' | 'end' | 'baseline' | 'stretch', `justify`: 'start' | 'center' | 'end' | 'between' | 'around' | 'evenly', `width`: float | 'NN%', `height`: float | 'NN%', `min_width`: float, `max_width`: float, `min_height`: float, `max_height`: float, `grow`: float, `shrink`: float, `wrap`: bool, `position`: 'relative' | 'absolute', `top`: float | 'NN%', `right`: float | 'NN%', `bottom`: float | 'NN%', `left`: float | 'NN%', `overflow`: 'visible' | 'hidden', `src`: str | PathLike | bytes, `fit`: 'contain' | 'cover' | 'fill' | 'none', `scroll`: 'x' | 'y' | 'both', `scroll_anchor`: bool, `stick_to_end`: bool, `reveal`: tuple[float, float]
- **Apariencia**: `bg`: color, `bg_hover`: color, `bg_pressed`: color, `gradient`: tuple[color, color, float], `radius`: float | str, `border_width`: float, `border_color`: color, `shadow`: tuple[float, float, float, color], `opacity`: float, `press_scale`: float, `transition`: Any, `animate_layout`: Any, `enter`: Any, `exit`: Any, `pulse`: Any, `scrollbar_color`: color, `placeholder_color`: color, `selection_color`: color, `tooltip`: str, `cursor`: 'default' | 'pointer' | 'text' | 'grab' | 'grabbing' | 'col-resize' | 'row-resize' | 'ns-resize' | 'ew-resize' | 'nesw-resize' | 'nwse-resize' | 'crosshair', `drop_target`: bool, `window_drag`: 'move' | 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw', `capture`: bool, `placement`: str, `offset`: float, `layer`: 'base' | 'overlay'
- **Texto**: `font_size`: float, `size` (= `font_size`), `font_weight`: float, `weight` (= `font_weight`), `color`: color, `font_family`: str, `family` (= `font_family`), `line_height`: float, `letter_spacing`: float, `focus_color`: color, `tooltip_bg`: color, `tooltip_color`: color, `max_lines`: int, `text_align`: 'left' | 'center' | 'right', `spans`: Any
- **Campos de texto**: `multiline`: bool, `placeholder`: str, `rows`: int
- **Foco**: `focusable`: bool, `autofocus`: bool
- **Accesibilidad**: `role`: str, `label`: str, `alt`: str, `description`: str, `value`: str | float, `checked`: bool, `selected`: bool, `expanded`: bool, `level`: int, `live`: 'polite' | 'assertive', `position_in_set`: int, `set_size`: int, `sort`: 'ascending' | 'descending', `orientation`: 'horizontal' | 'vertical', `modal`: bool, `hidden`: bool, `value_min`: float, `value_max`: float, `value_step`: float
- **Manejadores**: `on_click`, `on_drag`, `on_key`, `on_focus`, `on_blur`, `on_scroll`, `on_resize`, `on_drop`, `on_drop_hover`, `on_context_menu`, `on_change`, `on_submit`, `on_link`, `on_value`

## Tokens del tema

`MIDNIGHT` (oscuro, por defecto) y `DAYLIGHT` (claro) definen todos; `aurora docs tokens` explica
cómo crear un `Theme` propio.

- **Colores**: `$background`, `$surface`, `$surface_hover`, `$surface_pressed`, `$border`, `$text`, `$muted`, `$primary`, `$primary_hover`, `$primary_pressed`, `$accent`, `$success`, `$danger`, `$shadow`, `$glow`
- **Radios**: `$sm` (8), `$md` (12), `$lg` (18), `$full` (999)
