# Referencia

Referencia completa de la API pública de Aurora. Para un recorrido paso a paso, empieza por la
[guía](guide.md). Qué se considera público y cómo cambia entre versiones lo explica la
[política de estabilidad](stability.md).

- [App](#app)
- [Window (ventanas adicionales)](#window)
- [Diálogos nativos](#diálogos-nativos)
- [Bandeja del sistema](#bandeja-del-sistema)
- [Notificaciones](#notificaciones)
- [Menús nativos](#menús-nativos)
- [Signal](#signal)
- [component](#component)
- [Pilot (tests de interacción)](#pilot-tests-de-interacción)
- [Inspector y profiler de frames](#inspector-y-profiler-de-frames)
- [Hot reload](#hot-reload)
- [Primitivas](#primitivas)
- [Texto enriquecido](#texto-enriquecido)
- [Teclado y foco](#teclado-y-foco)
- [Accesibilidad](#accesibilidad)
- [Componentes](#componentes)
- [Animaciones](#animaciones)
- [Propiedades de estilo](#propiedades-de-estilo)
- [Temas y tokens](#temas-y-tokens)
- [Formatos de valores](#formatos-de-valores)
- [Empaquetado: `aurora build`](#empaquetado-aurora-build)
- [Avisos de obsolescencia](#avisos-de-obsolescencia)

---

## App

```python
App(view, *, title="Aurora", size=(960, 640), resizable=True, min_size=None, max_size=None,
    position=None, maximized=False, fullscreen=False, always_on_top=False, decorations=True,
    remember=None, theme=MIDNIGHT, menu=None, app_id=None, inspector=None, reload=None, motion=None)
```

| Parámetro | Tipo | Descripción |
|---|---|---|
| `view` | `Callable[[], Element]` | Función sin argumentos que devuelve el árbol de la interfaz. Se llama de nuevo tras cada evento. |
| `title` | `str` | Título de la ventana. |
| `size` | `tuple[float, float]` | Tamaño inicial en píxeles lógicos (independientes del DPI). |
| `resizable`, `min_size`, `max_size`, `position`, `maximized`, `fullscreen`, `always_on_top`, `decorations` | | Opciones de la ventana principal; las mismas que las de [`Window`](#opciones-de-ventana). `decorations=False` la deja [sin marco](#ventanas-sin-marco). |
| `remember` | `str \| None` | Recuerda entre sesiones el tamaño, la posición y si estaba maximizada la ventana principal, en una carpeta con ese nombre del directorio de configuración del usuario (ver [Recordar ventanas](#recordar-ventanas)). |
| `theme` | `Theme \| Callable[[], Theme]` | Tema fijo, o un `Signal[Theme]` para cambiarlo en caliente. |
| `menu` | `Sequence[dict] \| None` | La barra de menús nativa (Windows y macOS), descrita con [`menus`](#menús-nativos): `App(view, menu=menus.bar(...))`. En Linux no hay barra nativa. |
| `app_id` | `str \| None` | (Windows) El *AppUserModelID*: la identidad con la que Windows firma las [notificaciones](#notificaciones) y agrupa la barra de tareas. En una app empaquetada se deriva del título si no la indicas. |
| `inspector` | `bool \| None` | Permite abrir con F12 el [inspector y profiler de frames](#inspector-y-profiler-de-frames). Con `None` (por defecto) lo decide la variable de entorno `AURORA_INSPECTOR` (`1`, `true`, `yes` u `on` lo activan). |
| `reload` | `bool \| None` | Activa el [hot reload](#hot-reload) en `run()`. Con `None` (por defecto) lo decide la variable de entorno `AURORA_RELOAD`, como `inspector`. |
| `motion` | `bool \| None` | Con `False`, los componentes no animan por defecto ([switchs, casillas, pestañas y menús](#animaciones)): sus cambios son inmediatos. Con `None` (por defecto) lo decide `AURORA_MOTION` (`0`, `false`, `no` u `off` lo desactivan). |

| Método | Descripción |
|---|---|
| `run(*, backend="auto", keep_alive=None)` | Abre las ventanas y bloquea hasta que se cierren todas. `backend` elige dónde se pinta: `"gpu"` (Vulkan en Windows y Linux, Metal en macOS), `"cpu"` o `"auto"` (GPU si se puede iniciar; si no, CPU). Con `"auto"`, la variable de entorno `AURORA_BACKEND` (`gpu`/`cpu`) lo fuerza. `"gpu"` sin GPU disponible lanza `RuntimeError`; un valor desconocido, `ValueError`. `keep_alive=True` mantiene la app en marcha aunque no queden ventanas (para la bandeja del sistema) hasta que se llame a `quit()`. |
| `window(view, *, title="Aurora", size=None, resizable=True, min_size=None, max_size=None, position=None, maximized=False, fullscreen=False, always_on_top=False, decorations=True, remember=None, on_close=None)` | Crea una ventana adicional con su propia vista (ver [Window](#window)). `size` por defecto es el de la ventana principal. `remember="clave"` la [recuerda](#recordar-ventanas) junto a la principal (necesita `App(remember=...)`). |
| `windows()` | Las ventanas creadas con `window(...)`, en orden de creación (sin la principal). |
| `main` | La ventana principal, como un [`Window`](#window) (ver abajo). |
| `notify(title, body="", *, icon=None, on_click=None)` | Muestra una [notificación del sistema](#notificaciones). |
| `register_app_id(name=None)` | (Windows) Registra la identidad de la app con un acceso directo del menú Inicio (ver [Notificaciones](#notificaciones)). |
| `quit()` | Cierra todas las ventanas y termina la app. Seguro desde cualquier hilo. |
| `render_png(path, *, size=None, scale=2.0)` | Renderiza la vista a PNG sin abrir ventana. `scale` es la densidad de píxeles (2.0 ≈ pantalla Retina). |
| `pilot(*, size=None, scale=1.0, inspector=False)` | Ejecuta la app sin ventana y devuelve un [`Pilot`](#pilot-tests-de-interacción) para simular interacción en tests. Con `inspector=True`, el inspector se abre con `pilot.press("f12")` como en la ventana. |
| `watch(main=None)` | Activa el [hot reload](#hot-reload) del módulo `main` (por defecto, `__main__`) sin vigilar los archivos y devuelve su `Reloader`. Para probarlo con `pilot()`: `reloader.check()` detecta lo guardado y el siguiente frame lo aplica. |
| `spawn(coro)` | Ejecuta una corrutina en un bucle `asyncio` en segundo plano (un hilo propio, creado la primera vez). Devuelve un `concurrent.futures.Future` con su resultado. |

El elemento raíz siempre ocupa la ventana completa. Si no defines `bg`, `color` o `font_family`
en la raíz, se toman del tema (`$background`, `$text` y la fuente del tema).

## Window

```python
app = App(view, title="Notas", size=(420, 380))
detalle = app.window(detalle_view, title="Detalle", size=(320, 240))
```

Una ventana adicional, creada con [`App.window(...)`](#app). Tiene su propia vista y comparte con
la app el tema, el movimiento y los `Signal`: un cambio se ve en todas las ventanas a la vez. Las
creadas antes de `run()` se abren al arrancar; las creadas en marcha, al momento.

La ventana principal también se maneja así, a través de **`app.main`** (mismo `Window`, misma
API): `app.main.title = "…"` en marcha, `app.main.close()` para ocultarla si hay bandeja,
`app.main.open()` para volver a abrirla, o `app.main.on_close = fn` para confirmar antes de
cerrar. Su vista es la de la `App` (el hot reload la mantiene).

| Miembro | Descripción |
|---|---|
| `view` | La función de la vista de esta ventana (se puede sustituir). |
| `title` | El título. Asignarlo en marcha lo cambia al momento; seguro desde cualquier hilo. |
| `size` | `(ancho, alto)` del contenido (sin el marco) en píxeles lógicos. Abierta, da el tamaño real; asignarlo en marcha la redimensiona. |
| `position` | `(x, y)` de la esquina superior izquierda del marco en el escritorio, en píxeles lógicos, o `None` si la elige el sistema. Abierta, da la real; asignarla en marcha la mueve. |
| `maximized` | Si está maximizada. Abierta, da el estado real; asignarlo la maximiza o la restaura. |
| `fullscreen` | Si está en pantalla completa (sin bordes, en el monitor de la ventana; no cambia el modo de vídeo). |
| `always_on_top` | Si se queda encima de las demás ventanas. |
| `resizable` | Si el usuario puede redimensionarla. |
| `min_size` / `max_size` | Límites del tamaño del contenido al redimensionar, o `None` (sin límite). |
| `decorations` | Si lleva el marco y la barra de título del sistema. Con `False`, [sin marco](#ventanas-sin-marco). |
| `on_close` | Se llama al intentar cerrarla con el botón del sistema o `request_close()`; si devuelve un valor falso, el cierre se cancela —por ejemplo, para pedir confirmación con un `dialog`. |
| `is_open` | Si la ventana está abierta (o pendiente de abrir al arrancar la app). |
| `open()` / `close()` | La abre o la cierra (sin preguntar a `on_close`) sin olvidar su vista; seguras desde cualquier hilo. |
| `minimize()` | La minimiza, como su botón del sistema. |
| `request_close()` | Pide cerrarla como el botón del sistema: pasa antes por `on_close`. |
| `render_png(path, *, size=None, scale=2.0)` | Su vista a PNG, como `App.render_png`. |
| `pilot(*, size=None, scale=1.0, inspector=False)` | Su vista con un [`Pilot`](#pilot-tests-de-interacción) para tests de interacción. |

La app termina al cerrarse su última ventana (o con `app.quit()`), y el inspector (F12) es
independiente en cada ventana. Un ejemplo completo: [`examples/windows.py`](../examples/windows.py).

### Opciones de ventana

```python
app = App(view, size=(900, 600), min_size=(480, 360), remember="mi-app")
paleta = app.window(paleta_view, size=(240, 400), position=(40, 80), always_on_top=True)
app.main.fullscreen = True  # en marcha, desde cualquier hilo
```

`App(...)` (para la principal) y `app.window(...)` aceptan las mismas opciones, todas por nombre
y opcionales; cada una es también un miembro de `Window` que se lee y se cambia en marcha. Se
validan al crear o asignar: un tamaño no positivo, un valor no finito o un `min_size` mayor que
`max_size` lanzan `ValueError`, y lo que no es un par de números, `TypeError`. Al cerrar una
ventana se guarda cómo estaba (tamaño y posición restaurables, maximizada, pantalla completa):
`open()` la reabre igual.

`size` se recorta a `min_size`/`max_size`, y cambiar un límite en marcha ajusta la ventana si
queda fuera. Maximizada o en pantalla completa, el tamaño lo decide el sistema: en Windows ocupa
el monitor aunque haya `max_size` (usa `resizable=False` si no debe crecer).

Cada sistema pone sus límites:

- **Wayland** no deja que una app coloque sus ventanas ni sabe dónde están: `position` se ignora
  al crear y al asignar, y abierta lee `None` (o la última pedida).
- **macOS**: `always_on_top` sube la ventana sobre las normales, no sobre otras apps a pantalla
  completa; `fullscreen` usa la pantalla completa del sistema (un espacio propio).
- **Linux X11**: `maximized`, `always_on_top` y la posición dependen del gestor de ventanas; la
  mayoría los respeta.

### Recordar ventanas

`App(view, remember="mi-app")` recuerda entre sesiones el tamaño, la posición y si estaba
maximizada la ventana principal: al cerrarla (o al terminar la app) lo guarda, y al arrancar lo
restaura, por encima de `size`, `position` y `maximized`. Se guarda en
`<config>/mi-app/window-state.json`, donde `<config>` es el directorio de configuración del
usuario: `%APPDATA%` en Windows, `~/Library/Application Support` en macOS y `$XDG_CONFIG_HOME`
(o `~/.config`) en Linux. El nombre es el de esa carpeta: letras, números, espacios, `.`, `-` o
`_`.

- Una ventana adicional se recuerda con `app.window(..., remember="ajustes")`, en el mismo
  archivo (la clave `"main"` es la de la principal).
- Una posición recordada solo se usa si la barra de título sigue cayendo dentro de algún
  monitor (p. ej. si se desconectó el segundo); si no, la coloca el sistema.
- Se recuerda el tamaño de antes de maximizar: al restaurarla vuelve a él.
- La pantalla completa no se recuerda, ni nada si el proceso muere sin cerrar las ventanas. Un
  archivo ilegible se ignora y un error al escribirlo se avisa por stderr, sin romper la app.

### Ventanas sin marco

`decorations=False` (en `App(...)`, en `app.window(...)` o en marcha con `window.decorations`)
quita el marco y la barra de título del sistema para que la app pinte la suya. Hace falta decir
qué zona mueve la ventana y poner los botones; `title_bar(...)` lo trae hecho:

```python live size=520x200
from aurora import App, button, column, text, title_bar


def view():
    return column(grow=1)[
        title_bar("Notas", actions=button("Compartir", variant="ghost", padding=(4, 10))),
        column(grow=1, padding=24, gap=8)[
            text("Sin marco del sistema", size=18, weight=700),
            text("Arrastra la barra para moverla; doble clic para maximizar.", color="$muted"),
        ],
    ]


App(view, size=(520, 200), decorations=False).run()
```

- **Zonas de arrastre**: un elemento con `window_drag="move"` mueve la ventana al pulsarlo y la
  maximiza o la restaura con doble clic. Los controles de dentro (lo que tiene `on_click`,
  `on_drag`, es enfocable o editable) se quedan sus clics: un botón en la barra funciona igual.
  `window_drag="se"` (o `"n"`, `"s"`, `"e"`, `"w"`, `"ne"`, `"nw"`, `"sw"`) redimensiona desde ese
  borde, con su cursor: sirve para un agarre en una esquina.
- **Bordes**: una ventana sin marco y redimensionable se redimensiona desde una franja de 5 px en
  cada borde (12 px en las esquinas), por encima del contenido, como un marco de verdad. Maximizada,
  en pantalla completa o con `resizable=False`, no.
- **Botones**: `window.minimize()`, `window.maximized = not window.maximized` y
  `window.request_close()` (que pasa por `on_close`, como el botón del sistema) hacen lo que los
  del sistema. Dentro de una vista, [`current_window()`](#current_window) da su ventana.
- **En tests**, el piloto apunta lo que se pediría a la ventana en `pilot.window_requests`
  (`["move", "resize-se", "toggle-maximize"]`); con `App(..., decorations=False).pilot()` los
  bordes redimensionan como en la ventana.

Cada sistema tiene sus diferencias:

- **Windows**: la ventana conserva la sombra del sistema. Sin barra del sistema no hay menú de
  ventana con Alt+Espacio ni las disposiciones de Windows 11 al pasar sobre maximizar; arrastrarla
  al borde de la pantalla sí la ajusta.
- **macOS**: sin marco desaparecen también los «semáforos»: la ventana queda sin bordes y
  `title_bar` dibuja los suyos a la izquierda (`controls="windows"` o `"macos"` fija un estilo en
  todos los sistemas). Los bordes los redimensiona el propio sistema, así que las zonas
  `window_drag` de redimensionar no hacen nada.
- **Linux (Wayland)**: mover y redimensionar los hace el compositor y solo empiezan si el puntero
  está dentro de la ventana al pulsar (siempre lo está desde una zona). Con marco, Wayland pinta
  la barra del lado de la app (decoraciones de cliente) y algunos compositores (GNOME) la pintan
  sencilla.
- **Linux (X11)**: depende del gestor de ventanas; la mayoría permite mover y redimensionar, y el
  doble clic lo resuelve Aurora en todos.

La doble pulsación para maximizar la detecta Aurora (400 ms, como el doble clic de un campo), así
que se comporta igual en todos los sistemas, aunque el usuario haya configurado otra acción para
la barra de título del sistema.

#### `current_window()` { #current_window }

La [`Window`](#window) cuya vista se está construyendo (`app.main` para la principal). Sirve para
que un componente actúe sobre su propia ventana sin recibirla como argumento; solo se puede
llamar mientras se construye una vista (guárdala en una variable para usarla en un manejador).
Fuera, `RuntimeError`.

## Diálogos nativos

```python
from aurora import dialogs

ruta = dialogs.open_file(title="Abrir informe", filters=[("Texto", ["txt", "md"])])
```

Los diálogos del sistema para elegir archivos o carpetas:

| Función | Descripción |
|---|---|
| `open_file(*, title=None, directory=None, filters=None)` | Pide un archivo existente; devuelve su ruta o `None` si se cancela. |
| `open_files(*, title=None, directory=None, filters=None)` | Igual, con selección múltiple; devuelve una lista (vacía si se cancela). |
| `save_file(*, title=None, directory=None, default_name=None, filters=None)` | Pide dónde guardar y devuelve la ruta, o `None`. No escribe nada: guardar el contenido es cosa de quien llama. |
| `pick_folder(*, title=None, directory=None)` | Pide una carpeta; devuelve su ruta o `None`. |

`filters` son pares `(nombre, extensiones)`: `[("Imágenes", ["png", "jpg"]), ("Todo", ["*"])]`.
Su tipo es el alias **`dialogs.Filters`** (`Sequence[tuple[str, Sequence[str]]]`), útil para anotar
funciones propias que reciben filtros y los pasan a los diálogos.

Son **síncronas**: con el diálogo abierto la app espera (el sistema corre su propio bucle de
mensajes) y el GIL se suelta, así que los hilos y las corrutinas de `app.spawn` siguen trabajando.
La ventana desde la que se llaman (su vista o uno de sus manejadores) es su padre: el diálogo sale
modal sobre ella. Los pinta el sistema: en Linux usan el portal de escritorio (o `zenity` si no
hay portal) y en macOS aparecen con la app en primer plano. En los tests, sustitúyelas por un doble
—`monkeypatch.setattr(dialogs, "open_file", ...)`—: un test sin pantalla no puede abrir uno de
verdad.

## Bandeja del sistema

```python
from aurora import menus

app.tray(
    icon="icono.png",
    tooltip="Notas",
    menu=[
        menus.item("Abrir ventana", abrir),
        menus.separator(),
        menus.item("Salir", app.quit),
    ],
    on_click=lambda button: abrir(),
)
```

| API | Descripción |
|---|---|
| `app.tray(icon, *, tooltip=None, menu=None, on_click=None, on_double_click=None, template=False)` | Pone (o reemplaza) la bandeja. `icon` es una ruta o los bytes de un PNG/SVG (los dibuja Skia, como `image`). `menu` es una descripción de [`menus`](#menús-nativos). `on_click(button)` / `on_double_click(button)` reciben `"left"`, `"right"` o `"middle"`. `template=True` (macOS) pinta el icono con el color del sistema: dibújalo en blanco y negro con transparencia. |
| `app.tray_hide()` | Quita la bandeja. |

Mientras hay bandeja, la app **sigue viva aunque se cierren todas las ventanas** (es lo que
espera una app de bandeja): `app.quit()` la termina. `run(keep_alive=True)` también vale sin
bandeja, para una app que trabaja sin ventanas.

Con menú, el clic izquierdo suele abrirlo —en macOS siempre—; `on_click` se dispara con los clics
que no abre menú. En Linux la bandeja usa StatusNotifierItem: en GNOME hace falta la extensión
AppIndicator, y algunos escritorios no muestran la bandeja en absoluto.

## Notificaciones

```python
app.notify("Informe generado", "datos-2026.csv está en tu carpeta de descargas", icon="icono.png")
```

| API | Descripción |
|---|---|
| `app.notify(title, body="", *, icon=None, on_click=None)` | Muestra una notificación del sistema, con la identidad de la app. `icon` es una ruta a un PNG/SVG (donde el sistema lo admita). `on_click`, si se indica, se llama al pulsar el aviso. |
| `app.register_app_id(name=None)` | (Windows) Registra la identidad de la app con un acceso directo del menú Inicio: `%APPDATA%\...\Start Menu\Programs\<name>.lnk`. Devuelve `False` fuera de Windows o si no se pudo. |

Se puede llamar desde cualquier hilo —por ejemplo desde una tarea de `app.spawn()` con la ventana
cerrada— y también sin app en marcha. Si el sistema no admite notificaciones, se avisa por stderr
y la app sigue: en Linux hace falta un demonio de notificaciones (GNOME y KDE lo traen) y en macOS
una app firmada (un script suelto puede no poder mostrarlas).

**El clic en el aviso.** Con `on_click`, pulsar el cuerpo de la notificación llama a ese callback
(sin argumentos) desde un hilo propio: cambiar un `Signal` despierta la ventana sola. En Linux el
aviso declara la acción `default` —la que los servidores asocian al cuerpo y no dibujan como
botón—, y en macOS hace falta la app en marcha (`run()`) para que el sistema entregue el clic.
Cerrar el aviso sin pulsarlo no llama a nada.

**Windows y la identidad del aviso.** Windows firma cada notificación con el *AppUserModelID*
(AUMID) de quien la envía; sin uno propio, la identidad de reserva es la de PowerShell y el aviso
sale como **«Windows PowerShell»**. Por eso:

- `App(..., app_id="Mi.Aplicacion")` fija la identidad (avisos y agrupación de la barra de
  tareas). En una app **empaquetada** (`sys.frozen`, es decir `aurora build`), si no la indicas se
  deriva del título (`aurora.mi-aplicacion`) **y se registra sola** al arrancar.
- El registro es un **acceso directo del menú Inicio** con esa identidad: es lo que Windows exige
  a las apps sin instalador (y lo que le da nombre e icono al aviso). `app.register_app_id()` lo
  hace a mano; en desarrollo apunta a `python.exe` + el script, útil para probar la atribución.
  En un script sin identidad, el aviso lo firma «Windows PowerShell» (cosmético).

## Menús nativos

```python
app = App(
    view,
    menu=menus.bar(
        menus.submenu(
            "Archivo",
            menus.item("Abrir…", abrir, shortcut="mod+o"),
            menus.item("Guardar", guardar, shortcut="mod+s"),
            menus.separator(),
            menus.item("Salir", app.quit),
        ),
        menus.submenu("Edición", menus.predefined("copy"), menus.predefined("paste")),
    ),
)
```

| Constructor | Descripción |
|---|---|
| `menus.item(label, on_click, *, shortcut=None, enabled=True)` | Una opción; llama a `on_click()` al elegirla. `shortcut` es un atajo del sistema: `"ctrl+o"`, `"mod+s"` (`mod` es Control fuera de macOS y Comando en macOS), `"f5"`, `"shift+alt+f"`… |
| `menus.separator()` | Una línea separadora. |
| `menus.submenu(label, *items)` | Un submenú con sus entradas. |
| `menus.predefined(name)` | Una entrada estándar del sistema: `"copy"`, `"paste"`, `"cut"`, `"select_all"`, `"undo"`, `"redo"`, `"delete"`, `"minimize"`, `"maximize"`, `"fullscreen"`, `"close_window"`, `"quit"`, `"about"`, `"hide"`, `"hide_others"`, `"show_all"`, `"services"` o `"bring_all_to_front"`. Un nombre fuera de la lista lanza `ValueError`. La lista completa es el `frozenset` **`menus.PREDEFINED`** (`"copy" in menus.PREDEFINED`). |
| `menus.bar(*items)` | La barra de la app, para `App(menu=...)`; es azúcar de una lista. |

La misma descripción vale para los tres menús nativos:

- **La barra de la app**: `App(view, menu=menus.bar(...))`, en Windows y macOS. En macOS el núcleo
  añade delante el submenú estándar de la app (Acerca de, Ocultar, Salir…). Los atajos de la barra
  los gestiona el sistema, así que la app no los ve como teclas: no los repitas en `on_key`.
- **El menú de la bandeja**: `app.tray(icon, menu=[...])`.
- **Los menús contextuales**: la propiedad `on_context_menu` de cualquier elemento —clic derecho—
  con una lista o un callable que la devuelve (se evalúa al abrir el menú, así puede depender del
  estado):

```python
card(
    on_context_menu=[
        menus.item("Copiar", copiar),
        menus.separator(),
        menus.item("Eliminar", eliminar, enabled=hay_seleccion()),
    ],
)[...]
```

En Linux no hay menús nativos (requieren GTK): la barra y los contextuales no aparecen y el patrón
es el componente `menu` dentro de la interfaz. En macOS, con menú, el clic izquierdo de la bandeja
abre su menú.

## Signal

```python
count = Signal(0)
```

| API | Descripción |
|---|---|
| `count()` / `count.value` | Lee el valor actual. |
| `count.set(v)` | Asigna un valor. Si es igual al actual (`==`), no hace nada. |
| `count.update(fn)` | Atajo para `count.set(fn(count()))`. |
| `count.subscribe(fn)` | Llama a `fn(valor)` en cada cambio. Devuelve una función para cancelar la suscripción. |

La interfaz se reconstruye tras cada evento de usuario y tras cada `set` que cambie un valor;
los [`@component`](#component) que no dependan de lo que cambió se reutilizan.
`set` es seguro desde **cualquier hilo o corrutina**: despierta el bucle de eventos, así que un
`Signal` actualizado por un hilo de trabajo o por una tarea de `app.spawn()` se ve en pantalla sin
esperar a que el usuario mueva el ratón.

```python
status = Signal("cargando…")


async def load():
    data = await fetch_data()
    status.set(f"{len(data)} filas")


app = App(view)
app.spawn(load())
app.run()
```

## component

```python
@component
def fila(tarea: Tarea, seleccionada: bool):
    return row(key=f"tarea-{tarea.id}", bg="$surface" if seleccionada else None)[...]
```

Cuando `view()` se vuelve a llamar (ver [Reconstrucción parcial](#reconstrucción-parcial)), un
`@component` **no se reconstruye** si sus argumentos son iguales (`==`) a los de la última vez y no
cambió ningún `Signal` que leyera al construirse. Devuelve el mismo `Element`, que recuerda su
serialización, y el núcleo reutiliza el nodo ya procesado: el coste de esa rama en Python y en el
parseo desaparece. Si solo cambió lo que leen sus lambdas (textos, propiedades o hijos), se
reutiliza el `Element` y solo se vuelve a serializar. Es la forma de escalar listas grandes: en
una de 10 000 filas, cambiar la selección reconstruye 2 filas en vez de 10 000.

- Pasa como argumento lo que distingue a cada instancia (`seleccionada`) en vez de leer un
  `Signal` compartido dentro: un componente que lee `selected()` depende de él y se reconstruye
  cada vez que cambia.
- Los argumentos deben ser **hashables** (números, cadenas, tuplas, dataclasses congeladas). Con
  argumentos no hashables el componente funciona, pero no se memoriza.
- Depende solo de sus argumentos y de `Signal`. Si lee estado mutable normal (una lista global, un
  atributo de un objeto), no se entera de sus cambios.
- No pases lambdas creadas en cada llamada como argumento: son distintas cada vez. Créalas dentro
  del componente (`on_click=lambda: selected.set(tarea.id)`).
- Un componente puede contener otros: si cambia el de dentro, se reconstruye también el de fuera.
- Se olvidan las instancias que no aparecen en la última reconstrucción de la vista.

## Reconstrucción parcial

Las **funciones** dentro de la vista son regiones reactivas: se evalúan al serializar y anotan los
`Signal` que leen.

| Región | Ejemplo |
|---|---|
| Contenido de un texto | `text(lambda: f"{n()} clics")` |
| Una propiedad de estilo | `box(bg=lambda: "$success" if online() else "$danger")` |
| Un hijo calculado | `column()[lambda: [fila(t) for t in tareas()]]` (o un `Signal` de elementos) |

Cuándo la reconstrucción es parcial y cuándo completa:

| Qué cambió | Reconstrucción |
|---|---|
| Cualquier cosa tras un evento: un manejador `on_*` (clic, tecla, `on_change`, drop, `on_scroll`…), una opción de menú, la bandeja, un aviso, el cierre de una ventana | **Completa**: `view()` entera, como siempre (los `@component` se siguen memorizando) |
| Un `Signal` que solo leen regiones, sin evento: desde un hilo, una corrutina de `app.spawn` o un test entre frames del `Pilot` | **Parcial**: se reevalúan esas regiones |
| Un `Signal` que lee la propia `view()` (o un componente al construirse), el tema o la vista (hot reload) | **Completa** |

Tras un evento siempre es completa porque el manejador pudo cambiar, además de un `Signal`,
estado normal de Python que lee `view()` (una lista, un atributo), y eso no se puede detectar: la
vista nunca queda desactualizada. Un clic en una ventana hace completa la siguiente reconstrucción
de todas. Cuando es parcial, el resto del árbol reutiliza su serialización, en Python y en el
núcleo: en una vista de 50 000 nodos, cambiar el color de un punto desde un hilo cuesta unos
milisegundos en vez de reconstruirla entera.

```python
def view():
    return column()[
        text(f"{n()} clics"),  # lee `n` al construir: cambiarlo llama a view() entera
        text(lambda: f"{n()} clics"),  # región: un cambio de `n` sin evento solo reevalúa este texto
    ]
```

- Un hijo calculado devuelve lo mismo que admiten los corchetes (un elemento, una lista, `None`…)
  y ocupa su sitio entre sus hermanos. Lo que da se sustituye entero cuando se reevalúa; los
  `@component` que use dentro se siguen memorizando.
- Las keys, el foco, el scroll, los campos de texto y las transiciones se conservan igual que con
  una reconstrucción completa: salen del árbol que llega al núcleo.
- Un hilo o una corrutina que cambia estado normal de Python que lee `view()` necesita, como
  siempre, cambiar también un `Signal` que lea la vista (o ninguno que lea solo una región) para
  que se vea: si solo cambia uno que lee una región, la reconstrucción es parcial. Si un `Signal`
  no lo lee nadie, la vista se reconstruye entera.
- Los `chart` y los `canvas` se reenvían en cada reconstrucción, parcial o no: sus datos (un array
  modificado en el sitio) o su `draw` pueden cambiar sin avisar.
- `AURORA_PARTIAL=0` (u `off`, `false`, `no`) desactiva la reconstrucción parcial: la vista se
  llama entera en cada cambio, como en las versiones anteriores. Sirve para descartarla al depurar.

## Pilot (tests de interacción)

`app.pilot()` ejecuta la app **sin ventana** con el mismo runtime que la ventana real
(hit-testing, burbujeo, capas, reconstrucción) y simula el puntero frame a frame. Las coordenadas
están en píxeles lógicos y cada acción avanza un frame.

```python
def test_counter():
    pilot = App(view, size=(400, 300)).pilot()
    pilot.click("add")
    assert count() == 1
```

| API | Descripción |
|---|---|
| `click(key)` | Clic en el centro del nodo `key`, como una persona: si otro nodo lo tapa, el clic llega a ese otro. `LookupError` si el nodo no se pintó. |
| `click_at(x, y)` | Mueve el puntero, pulsa y suelta. |
| `drag(key, dx=0, dy=0, steps=4)` | Pulsa en el centro de `key`, mueve el puntero `(dx, dy)` en `steps` pasos y suelta. |
| `drag_to(key, to, steps=8)` | Arrastra desde el centro de `key` hasta el centro de otro nodo (`to`, su key) o hasta el punto `to=(x, y)`, y suelta. Para probar [`sortable`](#sortable): soltar sobre el centro de un elemento lo deja delante de él. |
| `window_requests` | Lo que las pulsaciones han pedido a la ventana, en orden: `"move"` (una zona `window_drag="move"`), `"resize-<borde>"` (`"resize-se"`…: un borde de una ventana [sin marco](#ventanas-sin-marco) o una zona de redimensionar) y `"toggle-maximize"` (doble clic en una zona que la mueve). |
| `hover_files(files)` | Archivos del sistema que entran arrastrándose en la ventana (`None`: salen sin soltar). Llama a los `on_drop_hover`. |
| `drop_files(files, key=None, at=None)` | Suelta archivos sobre el centro de `key`, en `at=(x, y)` o, sin ninguno, sin posición (como en macOS y Linux). Devuelve `True` si un `on_drop` los recibió. Ver [Soltar archivos](#soltar-archivos). |
| `cursor` | Cursor del ratón en el último frame: `"default"`, `"pointer"`, `"text"`, `"grab"`, `"grabbing"`, `"col-resize"`, `"row-resize"`, `"ns-resize"`, `"ew-resize"`, `"nesw-resize"`, `"nwse-resize"` (bordes de una ventana sin marco) o `"crosshair"` (modo selección del inspector). |
| `move_to(x, y)` / `leave()` | Mueve el puntero / lo saca de la ventana. |
| `mouse_down()` / `mouse_up()` | Pulsa / suelta el botón izquierdo por separado. |
| `wheel(dy=0, dx=0, *, lines=False)` | Rueda bajo el puntero; positivo = hacia el final del contenido. En píxeles (trackpad, inmediato) o, con `lines=True`, en pasos de rueda (animado). |
| `scroll(key, dy=0, dx=0)` | Mueve el puntero al centro de `key` y desplaza esos píxeles. |
| `scroll_offset(key)` | `(x, y)` desplazados del `scroll` con esa key, o `None`. |
| `chart_view(key)` | Ventana visible del eje x del `chart` con esa key, en unidades de datos (sin zoom, su dominio completo). |
| `press(combo)` | Pulsa y suelta una tecla o combinación: `"tab"`, `"shift+tab"`, `"enter"`, `"ctrl+s"`, `"a"`. |
| `key_down(combo)` / `key_up(combo)` | Pulsa / suelta por separado (p. ej. mantener Espacio). |
| `type(texto)` | Escribe en el campo enfocado, grafema a grafema, como desde el teclado (`"\n"` = Enter). |
| `ime_preedit(texto)` / `ime_commit(texto)` | Simulan la composición y la confirmación de un IME. |
| `selection(key)` | Selección del campo `key` en caracteres: `(inicio, fin)`, iguales si solo hay cursor. |
| `a11y_tree()` | El árbol de accesibilidad del último frame —lo que ve un lector de pantalla—: una lista de dicts por nodo con `id`, `key`, `role`, `label`, `value`, estados (`checked`, `selected`, `expanded`…), `live` (región viva: `"polite"`, `"assertive"` o `None`), `bounds` en píxeles lógicos, `actions`, `children` y `focused`. Lo decorativo no aparece. |
| `a11y_action(key, action, value=None)` | Pide una acción como un lector de pantalla sobre el nodo `key`: `"click"`, `"focus"`, `"blur"`, `"set_value"` (con `value`: texto o número), `"increment"`, `"decrement"`, `"expand"`, `"collapse"` o `"scroll_into_view"`. |
| `clipboard` | Portapapeles del piloto, en memoria (se puede leer y asignar); no toca el del sistema. |
| `focus(key)` | Enfoca `key` como si se llegara con el teclado. `LookupError` si no se pintó o no es enfocable. |
| `focused` | Key del nodo enfocado, o `None`. |
| `tooltip` | Texto del tooltip visible, o `None`. Avanza el tiempo con `frame(dt=0.6)` para que aparezca. |
| `hovered` | Key del nodo interactivo bajo el puntero, o `None`. |
| `rect(key)` | `(x, y, ancho, alto)` del nodo en el último frame, o `None`. |
| `frame(dt=1/60)` | Avanza un frame. Devuelve `True` si quedan transiciones en curso. |
| `settle()` | Avanza frames hasta que terminen todas las transiciones. |
| `resize(ancho, alto)` | Cambia el tamaño de la "ventana". |
| `png(path)` | Guarda el último frame como PNG. |
| `inspection` | Estado del inspector si el piloto se creó con `inspector=True` (si no, `None`): `open`, `pick` (modo selección), `selected` y `hovered` (keys), `rect` (caja del nodo elegido en el último frame) y `frames` (lista de `stats` de los últimos frames, solo con el panel abierto). |
| `stats` | Coste del último frame por fases, en milisegundos: `build` (tu `view()` y la serialización), `parse`, `style` (comparar el árbol nuevo con el anterior), `layout`, `draw` (las funciones `draw` de los `canvas` y la grabación de los `chart`), `paint` (composición y pintura) y `total` (la suma de todas); además `nodes` (nodos del árbol), `rebuilt` (si se reconstruyó la vista; si no, `build`, `parse` y `style` valen 0), `layout_cached` (si se reutilizó el layout del frame anterior) y `damage`, la zona repintada `(x, y, ancho, alto)` o `None` si el frame no pintó nada. Lo usa la [suite de benchmarks](../benchmarks/README.md). |

Las excepciones de la vista y de los manejadores **se propagan** al test (con ventana, se
imprimen y la app sigue viva).

## Inspector y profiler de frames

Con el inspector activado (`App(view, inspector=True)` o `AURORA_INSPECTOR=1`), **F12** acopla un
panel a la derecha de la ventana; la app ocupa el resto, sin quedar tapada. Desactivado (lo
habitual en una app distribuida), no cuesta nada y F12 no hace nada.

```bash
AURORA_INSPECTOR=1 uv run app.py
```

| Atajo | Acción |
|---|---|
| F12 | Abre y cierra el panel. |
| Ctrl+Mayús+C (Cmd+Mayús+C en macOS) | Entra y sale del **modo selección** (lo abre si está cerrado). También con el botón ⌖ del panel. |
| Escape | Sale del modo selección. |

- **Árbol**: los nodos de la vista en orden, con su tipo (`row`, `column`, `scroll`, `text`,
  `input`, `image`, `canvas`, `chart`), su key si es explícita y su texto. Las ramas se pliegan con
  la flecha. Un clic elige el nodo y muestra debajo su caja (`x`, `y`, ancho y alto en el último
  frame), su texto, su estilo tal como llegó al núcleo (tokens ya resueltos, con muestra de color)
  y sus eventos (`on_click`, `on_key`…). La lista es virtual: árboles de miles de nodos van fluidos.
- **Modo selección**: pasar el ratón por la app resalta el nodo pintado más arriba (contenido en
  azul, padding en verde, etiqueta con tipo, key y tamaño) sin hover ni llamadas a Python; un clic
  lo elige sin llegar a la app y el árbol se despliega y desplaza hasta él. El nodo elegido queda
  con un contorno rosa.
- **Frames**: coste por fases de los últimos 240 frames (`build` —tu `view()`—, `parse`, estilo,
  layout, `draw` y pintura) en barras apiladas frente al presupuesto de 60 fps (16,7 ms), con el
  último, la media, el p95 y el máximo, el desglose por fase y los datos del último frame (nodos,
  si reconstruyó la vista, si reutilizó el layout y la zona repintada). Son tiempos de CPU de
  Aurora, sin la presentación en pantalla. Los frames que no reconstruyen ni pintan nada no
  cuentan. Mientras llegan frames nuevos, el panel se refresca cada 250 ms (esos refrescos no se
  registran).

El panel se construye con las mismas primitivas que la app, así que su coste aparece en los
frames mientras está abierto (con la vista cerrada no hay ninguno). Con el panel abierto, la raíz
de la app pasa a ser hija de una fila: las keys por ruta llevan delante `0/` (`"0/0/1"` en vez de
`"0/1"`); las explícitas no cambian.

## Hot reload

Con el hot reload activado, **al guardar** el script de la app o cualquier módulo suyo, la ventana
se actualiza con el código nuevo en menos de medio segundo, **sin cerrarse y sin perder el estado**
de los `Signal`:

```bash
aurora dev app.py                 # o: AURORA_RELOAD=1 uv run app.py
aurora dev --inspector app.py     # también con el inspector (F12)
```

`aurora dev script [args...]` ejecuta el script como `python script` (con `__name__ == "__main__"`
y los argumentos que sigan) y activa el hot reload; las opciones de `aurora dev` van antes del
script. También se activa con `App(view, reload=True)`.

**Qué se recarga.** Se vigila el script principal y los módulos que importa desde su carpeta (y
subcarpetas), salvo los instalados (`site-packages`, el entorno virtual) y Aurora. Al cambiar uno,
se vuelven a ejecutar ese módulo, los módulos de la app que usan algo suyo (una función, una clase,
un objeto) y el script principal. Ahí `App(...)` y `app.run()` no abren otra ventana: la app en
marcha pasa a usar la `view` y el `theme` nuevos. El título y el tamaño no cambian. Con varias
ventanas, se emparejan con las del código nuevo por orden de creación (las demás se cierran o se
abren), y cada una pasa a usar la vista nueva.

**Qué se conserva.** Cada `Signal` del código nuevo que esté en el mismo sitio que uno del anterior
—una variable global, o un atributo o elemento (hasta 4 niveles) de un objeto de una clase de la
app, un dict o una lista— se sustituye por el antiguo: conserva su valor **y su identidad**, así
que los hilos, las corrutinas de `app.spawn` y los módulos que lo tenían guardado siguen usando el
mismo. Se queda con las suscripciones (`subscribe`) del código nuevo. Si el valor ya no es del
tipo del valor inicial nuevo (pasaste de `Signal(0)` a `Signal("")`), gana el nuevo. Cambiar solo
el valor inicial no reinicia el estado. También se conservan el foco, el scroll y las animaciones
de los nodos cuya key no cambie, como en cualquier reconstrucción.

**Qué no se conserva.** Los `Signal` locales (creados dentro de una función), el estado mutable
que no esté en un `Signal` y las instancias de clases redefinidas que guarde un `Signal` (siguen
siendo de la clase anterior: `isinstance` con la nueva da `False`).

**Errores.** Si el código nuevo no compila o falla al ejecutarse, los módulos vuelven a como
estaban y la ventana muestra el traceback (también se imprime en la consola). Con el hot reload
activado, una excepción en `view()` se muestra igual en vez de cerrar la app. Al guardar de nuevo
se reintenta. Los manejadores de eventos que fallan se imprimen, como siempre.

Desactivado no cuesta nada; activado, un hilo mira las fechas de modificación cada 300 ms. Es una
herramienta de desarrollo: una app empaquetada con `aurora build` no debería activarlo.

## Primitivas

Todas devuelven un `Element`. Los hijos se añaden con corchetes:

```python live
from aurora import column, text  # oculto

column(gap=8)[text("a"), text("b")]
```

Dentro de los corchetes se aceptan elementos, listas (se aplanan), strings (se convierten en
`text`), `None`/`False` (se ignoran, para poder escribir `condición and elemento`) y funciones sin
argumentos que devuelven cualquiera de esas cosas: son hijos calculados, que se reevalúan solos
cuando cambia un `Signal` que leen ([reconstrucción parcial](#reconstrucción-parcial)). Cualquier
propiedad de estilo admite también una función (`bg=lambda: ...`), con el mismo efecto.

| Primitiva | Descripción |
|---|---|
| `box(**estilo)` | Contenedor genérico. Apila sus hijos en **columna** por defecto. |
| `column(**estilo)` | Contenedor con `direction="column"`. |
| `row(**estilo)` | Contenedor con `direction="row"`. |
| `text(contenido, **estilo)` | Texto. `contenido` puede ser un `str` o un callable (`lambda: f"{x()}"`), que se evalúa al serializar y se reevalúa solo cuando cambia lo que lee ([reconstrucción parcial](#reconstrucción-parcial)). Para varios estilos en un párrafo, [`rich_text`](#rich_text). |
| `spacer()` | Caja con `grow=1`: ocupa todo el espacio libre del eje principal. |
| `scroll(*, axis="y", **estilo)` | Contenedor desplazable (rueda, trackpad y barra arrastrable). Ver abajo. |
| `image(src, *, fit="contain", **estilo)` | Imagen de un archivo o de bytes. Ver abajo. |
| `canvas(draw, **estilo)` | Lienzo de dibujo inmediato. Ver abajo. |
| `chart(y, *, kind="line", **estilo)` | Gráfico nativo (línea, área, barras, dispersión) alimentado por arrays. Ver abajo. |

`Element` es la clase de todo lo que devuelven las primitivas y los componentes; no hace falta
crearla a mano. Para anotar funciones de vista, `-> Element`. Expone `key`, `kind`, `style` (las
propiedades), `children`, `handlers` (los `on_<evento>`, sin el prefijo: `el.handlers["click"]`) y
`on_click` (atajo de `handlers.get("click")`), útiles en tests de la vista sin piloto.
`el.to_spec(theme)` lo serializa al dict que recibe el núcleo, con los tokens del tema y las
funciones ya resueltos: es lo que se depura al ver qué llega a Rust.

### `image(src, *, fit="contain", **estilo)`

Muestra una imagen **PNG, JPEG, WebP, GIF** (primer fotograma), **BMP, ICO o SVG**. `src` es una
ruta (`str` o `Path`) o `bytes` con el archivo ya en memoria (p. ej. una gráfica generada con
matplotlib).

```python
image("assets/logo.svg", width=32)
image(cover_path, height=160, fit="cover", radius="$lg")
image(png_bytes)
```

- **Tamaño:** sin `width` ni `height`, ocupa su tamaño natural (1 píxel de la imagen = 1 píxel
  lógico) sin pasar del ancho disponible, como `max-width: 100%` en CSS. Con uno de los dos, el
  otro sale de su proporción. Sin `width`, no se estira en el eje cruzado de su contenedor.
- **`fit`** decide cómo encaja cuando fijas los dos lados: `"contain"` (entera, sin deformar,
  con márgenes si hace falta), `"cover"` (llena la caja recortando lo que sobra), `"fill"`
  (estirada) o `"none"` (tamaño natural, centrada y recortada).
- Se recorta a las esquinas del elemento: con `radius="$full"` y `fit="cover"` tienes un avatar.
- Los SVG se pintan como vectores: se ven nítidos a cualquier tamaño y densidad de pantalla. Su
  tamaño natural sale de `width`/`height` o, si no los tienen, del `viewBox`.
- Cada imagen se decodifica **una vez** y se reutiliza entre reconstrucciones. Si el archivo
  cambia en disco, se vuelve a leer en la siguiente reconstrucción.
- Un archivo que no existe lanza `FileNotFoundError`, y uno que no se puede decodificar,
  `ValueError`, ambos con la ruta en el mensaje.
- Una ruta relativa se resuelve desde el directorio de trabajo. Para los recursos de tu app usa
  [`resource()`](#resourcepath), que funciona igual con Python y en el ejecutable empaquetado.

### `canvas(draw, **estilo)`

Lienzo de **dibujo inmediato**: `draw(c)` recibe un `Canvas` del tamaño de la caja y dibuja en él
con comandos sueltos, como un `<canvas>` de HTML. Para gráficos, indicadores, diagramas o
cualquier cosa que no sea una composición de cajas.

```python live align=stretch size=480
from aurora import Canvas, canvas

values = [0.2, 0.35, 0.3, 0.9, 0.5, 0.7, 0.62, 0.55, 0.4]  # oculto


def sparkline(c: Canvas):
    step = c.width / (len(values) - 1)
    points = [(i * step, c.height - v * c.height) for i, v in enumerate(values)]
    c.polyline(points, stroke="$primary", stroke_width=2)
    c.text(c.width, 0, "máx.", align="right", size=11, color="$muted")


canvas(sparkline, height=60, bg="$surface", radius="$md", padding=8)
```

- **Coordenadas:** píxeles lógicos con el origen en la esquina superior izquierda de la caja de
  contenido (dentro del `padding`) y el eje y hacia abajo. `c.width` y `c.height` son su tamaño.
  Lo que se sale se recorta (también a las esquinas redondeadas).
- **Tamaño:** sin `height`, `grow`, `min_height` ni `max_height` mide 200 px de alto; a lo ancho
  se estira como cualquier caja. Admite el estilo de una caja (`bg`, `radius`, `border_*`,
  `shadow`…), manejadores (`on_click`…) e hijos con `[...]`, que se pintan encima del dibujo.
- **Cuándo se llama a `draw`:** después del layout (por eso ya conoce su tamaño), cada vez que
  la vista se reconstruye y cuando el lienzo cambia de tamaño. Hover, scroll y animaciones de
  otros nodos **no** lo llaman: el dibujo grabado se repinta sin volver a Python. Dentro de un
  `@component` que no se reconstruye, `draw` solo se repite si cambia el tamaño o algún `Signal`
  que lea la propia función.
- **En lote:** los comandos se acumulan en Python y cruzan al núcleo de una vez, donde se graban
  en un `Picture` de Skia. Las listas de puntos viajan como un bloque de `float32`; un array de
  numpy de forma `(n, 2)` se convierte sin recorrerlo en Python.
- Un comando inválido (color desconocido, `dash` impar…) lanza `ValueError`; una excepción en
  `draw` se propaga como las de la vista.

Métodos de `Canvas`. Los colores aceptan tokens (`"$primary"`) y hex con alfa. Las figuras se
rellenan con `fill`, se perfilan con `stroke` (de grosor `stroke_width`) o ambas cosas; sin
ninguno de los dos usan `$primary` (rellenas las figuras cerradas, trazadas las líneas y arcos).
`dash=(on, off, ...)` hace el trazo discontinuo.

| Método | Descripción |
|---|---|
| `clear(color="$background")` | Rellena todo el lienzo. |
| `rect(x, y, w, h, *, radius=0, fill, stroke, stroke_width=1, dash)` | Rectángulo, con esquinas redondeadas opcionales. |
| `oval(x, y, w, h, ...)` / `circle(cx, cy, r, ...)` | Elipse inscrita en el rectángulo / círculo. |
| `arc(cx, cy, r, start, sweep, *, pie=False, ..., cap="butt")` | Arco (grados, 0 = derecha, sentido horario). `pie=True` lo cierra por el centro. |
| `line(x1, y1, x2, y2, *, stroke="$primary", stroke_width=1, cap="butt", dash)` | Segmento. |
| `polyline(points, *, stroke, fill, stroke_width=1, closed=False, cap, join="round", dash)` | Línea quebrada por `[(x, y), ...]` o un array `(n, 2)`. |
| `polygon(points, *, fill, stroke, ...)` | Polígono cerrado y relleno. |
| `path(path, *, fill, stroke, ...)` | Trazado libre (`Path`, abajo). |
| `text(x, y, content, *, color="$text", size=14, weight=400, family=None, align="left", baseline="top")` | Una línea de texto. `align` (`"left"`, `"center"`, `"right"`) la coloca respecto a `x`; `baseline` (`"top"`, `"middle"`, `"alphabetic"`, `"bottom"`) respecto a `y`. La familia por defecto es la del tema. |
| `save()` / `restore()` / `saved()` | Guardan y recuperan la transformación y el recorte. `with c.saved(): ...` hace las dos cosas. |
| `translate(dx, dy)` / `scale(sx, sy=None)` / `rotate(grados)` | Transforman lo que se dibuje después. |
| `clip_rect(x, y, w, h)` | Recorta lo que se dibuje después (hasta el próximo `restore`). |

`cap`: `"butt"`, `"round"` o `"square"`; `join`: `"miter"`, `"round"` o `"bevel"`.

`Path()` construye trazados encadenando `move_to(x, y)`, `line_to(x, y)`,
`quad_to(cx, cy, x, y)`, `cubic_to(c1x, c1y, c2x, c2y, x, y)`, `arc(cx, cy, r, start, sweep)` y
`close()`:

```python
c.path(Path().move_to(0, 40).quad_to(30, 0, 60, 40).close(), fill="$accent")
```

### `chart(y, *, x=None, kind="line", **estilo)`

Gráfico nativo: **línea**, **área**, **barras** o **dispersión**, con los ejes, la rejilla y la
leyenda calculados solos. Los datos se leen de los arrays **sin copiarlos**.

```python
from aurora import chart

chart(ventas(), height=160)  # una línea
chart(df, names=["p50", "p95"], kind="area")  # varias series de un DataFrame
chart(cierres, labels=DIAS, kind="bar", height=140)
chart(ys, x=xs, kind="scatter", point_size=3)
chart(muestras, zoom=True)  # millones de puntos: rueda para acercar, arrastra para mover
```

- **Datos:** `y` puede ser un array de numpy, un `array.array`, un `memoryview` o una lista; una
  `Series` o un `DataFrame` de polars (o cualquier cosa con `to_numpy()`, como pandas — un
  DataFrame aporta **una serie por columna**); una **lista de series**; o un array 2-D `(n, m)`,
  una serie por columna. Los datos cruzan al núcleo **sin copiarse**: el gráfico lee la memoria
  del array, así que mutarlo en sitio y reconstruir la vista basta para actualizarlo (los de
  polars se convierten con `to_numpy()`, que comparte memoria cuando el tipo lo permite). Los
  valores que falten (`NaN`) se saltan y, en una línea o un área, la cortan.
- **Millones de puntos:** al grabar, cada serie se reduce en Rust con **LTTB**
  (*Largest-Triangle-Three-Buckets*) a ~2 puntos por píxel: el perfil y los picos se conservan y
  solo se recorren los puntos visibles (con x ordenada, por búsqueda binaria). Un gráfico de un
  millón de puntos se graba en milisegundos y se mueve a 60 fps.
- **Zoom y pan:** con `zoom=True`, la rueda acerca y aleja sobre el puntero (el dato bajo el
  cursor no se mueve), el arrastre desplaza la ventana, la rueda horizontal (trackpad) también
  desplaza y el doble clic vuelve a la vista completa. El eje y se ajusta a lo visible salvo que
  fijes `y_min`/`y_max`; al llegar a un tope, la rueda pasa al `scroll` de fuera. El gráfico entra
  en el orden de Tab y, con el foco, `+` (o `=`) y `-` acercan y alejan alrededor del centro, ← y
  → desplazan un 10 % de lo visible y `0` o Inicio vuelven a la vista completa (`focusable=False`
  lo saca del orden de Tab; un `on_key` que atienda la tecla la gana). Para los lectores de
  pantalla, su valor es la ventana visible (`"Zoom 2×: 10 – 30"`, con las `labels` si las hay),
  que una región viva (`f"{key}#zoom"`) anuncia al cambiar, y su descripción explica las teclas.
  La ventana es estado del gráfico (su `key`) y sobrevive a las reconstrucciones;
  `Pilot.chart_view(key)` la lee en los tests.
- **Series:** `color` admite un color o una lista (uno por serie; sin él, rota la paleta del
  tema) y `names` dibuja la leyenda de arriba.
- **Ejes:** el de x son posiciones 0, 1, 2… salvo que des `x` (numérico) o `labels` (categorías:
  meses, días…). El de y sale de los datos, con ticks redondos, o de `y_min`/`y_max` (los dos
  juntos deben ser coherentes). Las barras siempre nacen del cero y, con varias series, se
  agrupan (una al lado de otra). `grid=False` quita la rejilla.
- **Aspecto:** `stroke_width` (grosor de la línea, 2), `point_size` (radio de la dispersión, 3.5),
  `bar_width` (fracción del hueco de cada barra, 0.7), `label_size`, `label_color` y `grid_color`;
  admite el estilo de una caja (`bg`, `radius`, `padding`, `border_*`…) y manejadores como
  `on_click` (que recibe el clic en el gráfico, no en cada barra).
- **Tamaño:** sin `height`, `grow`, `min_height` ni `max_height` mide 200 px de alto; a lo ancho
  se estira como cualquier caja (en una `row`, dale `grow=1` o `width`).
- **Cuándo se vuelve a grabar:** cuando la vista se reconstruye con otros datos u opciones, cuando
  cambia su caja o cuando la rueda o el arrastre mueven la ventana. Hover, scroll y animaciones de
  otros nodos lo repintan sin releer los datos. Dentro de un `@component`, solo si cambian sus
  argumentos o algún `Signal` que lea.
- Un dato no numérico (texto, complejos…), unas `labels` que no encajen con los puntos o una
  `kind` desconocida lanzan `ValueError` (`TypeError` si los datos no son ni números ni arrays).

```python live align=stretch
import numpy as np

from aurora import chart

rng = np.random.default_rng(7)
precios = 100 + np.cumsum(rng.normal(0.15, 1, size=(250, 2)), axis=0)  # dos series, una por columna
chart(precios, names=["Aurora", "Índice"], height=200)
```

Ejemplo completo en [`examples/charts.py`](../examples/charts.py).

### `scroll(*, axis="y", **estilo)`

Recorta su contenido a su caja (respetando `radius` y `border_width`) y lo desplaza en el eje
`axis`: `"y"` (vertical), `"x"` (horizontal) o `"both"`.

- Apila sus hijos en el eje que se desplaza (`direction="row"` con `axis="x"`) y **no los encoge**
  para que quepan: lo que sobra se desplaza. El `padding` forma parte del contenido desplazable.
- Uno vertical sin `height` ni `max_height` ocupa el espacio libre (`grow=1`). Con `height` o
  `max_height` tiene ese tamaño.
- La rueda del ratón se desplaza con suavizado; el trackpad, píxel a píxel (en macOS, con la inercia
  del sistema). Al llegar al límite, el desplazamiento pasa al `scroll` que lo contiene. Una rueda
  vertical también desplaza un `scroll` solo horizontal.
- La barra se superpone al contenido sin ocupar espacio. Aparece al desplazarse o al acercar el
  puntero al borde, y se oculta sola. Se puede arrastrar; pulsar fuera del pulgar lo lleva al puntero.
- Los hijos que quedan fuera de la zona visible no reciben clics ni hover.
- Dale una `key` para conservar la posición si el `scroll` cambia de sitio en el árbol. Si el
  contenido se encoge, la posición se ajusta sola.
- `on_scroll` recibe un `ScrollEvent` (`x`, `y`: desplazamiento; `width`, `height`: tamaño de la
  zona visible, en píxeles lógicos) en el primer frame y cada vez que alguno cambia. A diferencia
  de los demás manejadores no reconstruye la vista por sí solo (se llama en cada frame de
  desplazamiento): si cambias un `Signal` en él, la vista se reconstruye en ese mismo frame. Para
  listas muy largas, [`virtual_list`](#virtual_list)
  ya lo usa por ti.

```python
scroll(key="log", max_height=240, gap=6)[[text(line) for line in lines()]]
scroll(axis="x", gap=12)[[card(width=200)[...] for item in items()]]
```

Además de las propiedades de estilo, todos los elementos aceptan:

| Argumento | Descripción |
|---|---|
| `on_scroll` | En un `scroll`: callable que recibe un `ScrollEvent` cuando cambian el desplazamiento o la zona visible. Ver [`scroll`](#scroll-axisy-estilo). |
| `on_resize` | Callable que recibe un `ResizeEvent` (`width`, `height`: tamaño de la caja del elemento) cuando el layout le da otro tamaño, también la primera vez que se maqueta. Para adaptar la vista al espacio disponible (lo usa `splitter`). Como `on_scroll`, no reconstruye la vista por sí solo: cambia un `Signal` si hace falta. |
| `on_click` | Callable sin argumentos. Hace al elemento interactivo: cursor de mano, estados hover/pressed y clics. |
| `on_drag` | Callable que recibe un [`DragEvent`](#dragevent). Pulsar sobre el elemento empieza un arrastre: le llegan todos los movimientos hasta soltar, aunque el puntero salga de su caja. Si el puntero llega a moverse, el gesto no cuenta como clic. Hace al elemento interactivo (hover/pressed) pero no enfocable. |
| `on_key` | Callable que recibe un [`KeyEvent`](#keyevent). Recibe las teclas cuando el foco está en el elemento o en uno de sus descendientes (la raíz las recibe siempre). Devuelve `True` para darla por atendida. |
| `on_focus` / `on_blur` | Callables sin argumentos: el elemento gana / pierde el foco. |
| `on_drop` | Callable que recibe la lista de rutas (`list[str]`) de los archivos que se sueltan desde el explorador del sistema sobre el elemento o sus hijos. Ver [Soltar archivos](#soltar-archivos). |
| `on_drop_hover` | Callable que recibe la lista de rutas cuando un arrastre de archivos entra en la ventana y `None` cuando sale o se suelta. Para resaltar las zonas donde soltar. |
| `on_<evento>` | Todo argumento que empiece por `on_` se trata como manejador, no como estilo. |
| `focusable` | `bool`. Si el elemento recibe el foco con Tab y con clic. Por defecto, los que tienen `on_click`, los campos de texto y los `chart(zoom=True)`. |
| `autofocus` | `bool`. Toma el foco al aparecer en la vista (p. ej. el primer botón de un diálogo). Solo al aparecer: no lo roba en cada reconstrucción. |
| `role` | Rol de accesibilidad para los lectores de pantalla: `"button"`, `"checkbox"`, `"switch"`, `"radio"`, `"radiogroup"`, `"slider"`, `"textbox"`, `"combobox"`, `"option"`, `"tab"`, `"tablist"`, `"dialog"`, `"menu"`, `"menuitem"`, `"list"`, `"listitem"`, `"table"`, `"row"`, `"cell"`, `"columnheader"`, `"progressbar"`, `"image"`, `"heading"`, `"status"`, `"link"`, `"region"`, `"separator"`… (los nombres de ARIA en minúscula). Un rol desconocido lanza `ValueError`. Ver [Accesibilidad](#accesibilidad). |
| `label` | Nombre con el que el lector anuncia el elemento. Por defecto, su texto (`text`, o el de un botón o casilla). En los controles compuestos (`select`, `combobox`, `number_input`, los selectores de fecha, hora y color) va al nodo que tiene el rol, y `field(..., label=)` lo pone en el control que envuelve. |
| `description` | Texto secundario de ayuda; si no se indica, el `tooltip` hace de descripción. |
| `value` | Valor anunciado: texto (`"3 de 10"`) o número (`0.5`). En un campo de texto, el valor es lo que hay escrito. |
| `checked` | `bool`. Estado de `checkbox` y `switch` (las casillas y los interruptores lo ponen solos). |
| `selected` | `bool`. Estado de `tab` y `option` (pestañas, desplegables). |
| `expanded` | `bool`. Estado de `combobox` y `button` de acordeón. |
| `level` | Nivel de un `heading` (1 = título principal). |
| `live` | `"polite"` o `"assertive"`: región viva — sus cambios se anuncian solos (lo usan `toast`). |
| `position_in_set` / `set_size` | Posición y tamaño del conjunto: «elemento 3 de 100» (`radio`, `virtual_list` y `table` los ponen solos). |
| `sort` | `"ascending"` o `"descending"` en una cabecera ordenada (`table`). |
| `orientation` | `"horizontal"` o `"vertical"`: orientación de un `"separator"` (`splitter`) o de una barra. |
| `modal` | `bool`. El diálogo bloquea el resto de la interfaz (lo pone `dialog`). |
| `value_min` / `value_max` / `value_step` | Rango de un `slider` o una barra de progreso, y paso de las acciones de ajuste. |
| `hidden` | `bool`. Fuera del árbol de accesibilidad: decorativo (el contenido visual no cambia). |
| `alt` | En una imagen, texto alternativo (equivale a `label`). Sin `alt` ni `label`, la imagen es decorativa y no se anuncia. |
| `key` | Identidad estable. Conserva el estado de animación aunque el elemento cambie de posición en el árbol. Recomendado en listas dinámicas. Un elemento sin `key` recibe la de su padre seguida de su posición (`"fila-7/0"`, `"fila-7/1"`…), así que los hijos siguen a su padre si este se mueve. |

### `DragEvent`

Lo que reciben los manejadores `on_drag`, en píxeles lógicos:

| Atributo | Descripción |
|---|---|
| `phase` | `"start"` al pulsar, `"move"` en cada movimiento y `"end"` al soltar. |
| `x`, `y` | Posición actual del puntero en la ventana. |
| `dx`, `dy` | Desplazamiento desde donde se pulsó (no desde el último evento). |
| `target` | Key de la zona de soltar (un elemento con `drop_target=True`) más cercana bajo el puntero, o `None`. El elemento arrastrado y lo que lleva dentro no cuentan ni tapan lo que hay debajo: puede ir pegado al puntero como vista previa. |
| `index` | Con `target`, la posición en la que caería: cuántos hijos arrastrables (con `on_drag`) de la zona, sin contar el arrastrado, tienen el centro antes del puntero en el eje de la zona. Si no, `None`. |

Con `target` e `index`, el núcleo resuelve lo único que Python no puede saber (la geometría);
[`sortable`](#sortable) construye encima las listas reordenables y los tableros.

```python
ancho = Signal(240.0)
inicio = {}


def redimensionar(e: DragEvent):
    if e.phase == "start":
        inicio["ancho"] = ancho()
    ancho.set(max(120, inicio["ancho"] + e.dx))


row()[
    column(width=ancho())[...],
    box(width=6, cursor="col-resize", bg_hover="$border", on_drag=redimensionar),
]
```

### Soltar archivos

Arrastrar archivos desde el explorador del sistema hasta la ventana los entrega al elemento con
`on_drop` que hay bajo el puntero (o a su primer ancestro que lo tenga), como una lista de rutas
absolutas. Mientras el arrastre pasa sobre la ventana, todos los `on_drop_hover` de la vista
reciben esas rutas, y `None` al salir o al soltar:

```python
arrastrando = Signal(False)
archivos = Signal[list[str]]([])

card(
    padding=24,
    border_width=2,
    border_color="$primary" if arrastrando() else "$border",
    on_drop=archivos.set,
    on_drop_hover=lambda rutas: arrastrando.set(rutas is not None),
)[text("Suelta aquí tus CSV")]
```

- **Dónde cae**: en Windows, en el punto exacto donde se suelta. En macOS y Linux (X11) el sistema
  no informa del punto durante el arrastre: los archivos van al **primer elemento con `on_drop`
  de la vista** (en orden del árbol), así que con una sola zona se comporta igual en todos los
  sistemas. Por la misma razón, `on_drop_hover` avisa a la vista entera, no a la zona de debajo.
- **Linux con Wayland**: winit todavía no entrega los archivos arrastrados; ni `on_drop` ni
  `on_drop_hover` se llaman (con XWayland sí).
- Solo se entregan archivos y carpetas (no texto ni imágenes arrastradas desde otra app). Lo que
  haya en las rutas lo decide tu manejador: comprueba la extensión antes de abrirlas.
- En los tests, `pilot.hover_files(rutas)` / `pilot.hover_files(None)` y
  `pilot.drop_files(rutas, key=...)` simulan el arrastre (sin `key` ni `at`, sin posición, como en
  macOS y Linux); `drop_files` devuelve si algún `on_drop` los recibió.

## Texto enriquecido

### `rich_text(*partes, key=None, **estilo)` { #rich_text }

Un párrafo con **tramos de estilos distintos**: cada parte es un texto (con el estilo del
párrafo), un `span(...)` o una lista de ellos. Todo es un único nodo de texto, así que el núcleo
lo compone y lo parte en líneas entero: los cambios de peso, color o fuente no rompen el ajuste de
línea, y un tramo puede partirse entre dos líneas. Los `estilo` son los de `text` (`size`, `color`,
`line_height`, `max_lines`, `text_align`…) y valen para los tramos que no los fijan.

```python live
from aurora import App, column, rich_text, span


def view():
    return column(padding=20, width=340)[
        rich_text(
            "Pulsa ",
            span("Guardar", weight=700),
            " o ",
            span("descarta los cambios", on_click=lambda: print("descartar")),
            ". La configuración vive en ",
            span("config.toml", code=True),
            " y ",
            span("no se sincroniza", italic=True, color="$danger"),
            ".",
            line_height=1.5,
        )
    ]


App(view, size=(380, 100)).run()
```

#### `span(content, *, weight=None, color=None, italic=False, underline=False, strike=False, code=False, size=None, family=None, bg=None, on_click=None)`

Un tramo de `rich_text` (devuelve un `Span`, una dataclass inmutable con esos mismos campos). Lo que
no se fija se hereda del párrafo. `bg` pinta un fondo detrás de sus
letras; `code=True` lo escribe en monoespaciada sobre `$surface_hover` (la constante `MONO` de
`aurora.richtext` es esa lista de fuentes). Con `on_click` el tramo es un **enlace**: en `$primary`
y subrayado (salvo que se fije otro `color` o `underline`), con cursor de mano, recibe clics en
todas las líneas que ocupe y se anuncia como `"link"` (con su texto como nombre) a los lectores de
pantalla, que pueden activarlo. Entra en el orden de Tab (una sola parada aunque ocupe varias
líneas, con el anillo de foco alrededor de cada una) y se activa con Enter. Las zonas de los
enlaces tienen la key `f"{key}#link-{n}-{parte}"` (`n`, el orden del enlace en el párrafo; `parte`,
el trozo por línea), útil con `Pilot.click`; el enlace enfocado es el de `parte` 0, el que dan
`Pilot.focused` y `Pilot.focus`.

### `markdown(source, *, on_link=None, gap=12, key=None, **estilo)` { #markdown }

Render de Markdown básico, en Python sobre `rich_text` y sin dependencias: títulos (`#` a
`######`), párrafos, listas con viñetas y numeradas (anidadas por sangría), citas (`>`), código en
línea y en bloque (con ```` ``` ```` o `~~~`), separadores (`---`), énfasis (`*cursiva*`,
`**negrita**`, `~~tachado~~`), enlaces y escapes con `\`. Devuelve una columna (los `estilo` van a
ella y `gap` separa los bloques) cuyos párrafos se ajustan al ancho disponible.

Los enlaces llaman a `on_link(url)`; sin él, los `http(s)://` y `mailto:` se abren en el navegador
y el resto se ignora. Para los lectores de pantalla, los títulos son `"heading"`s con su nivel y
las listas, `"list"`s de `"listitem"`s. No admite tablas, imágenes ni HTML (su texto se muestra tal
cual).

```python live
from aurora import App, column, markdown

NOTAS = """
## Novedades

La versión trae **texto enriquecido** y un render de *Markdown*:

- tramos con `código`, ~~tachado~~ y [enlaces](https://example.com)
- listas anidadas:
  1. numeradas
  2. y con viñetas

> Los párrafos se parten al ancho disponible.
"""


def view():
    return column(padding=20, width=420)[markdown(NOTAS)]


App(view, size=(460, 260)).run()
```

## Teclado y foco

Un elemento enfocado recibe el teclado. Se enfoca **con Tab / Shift+Tab** (en orden de pintura,
volviendo al principio al final) o **con un clic**; un clic en una zona sin elementos enfocables
quita el foco. Al llegar con el teclado se dibuja un **anillo de foco** animado, del color
heredable `focus_color` (`$primary` por defecto); con un clic no, como `:focus-visible` en CSS.
Si el elemento está dentro de un `scroll`, este se desplaza para mostrarlo.

Cada tecla pasa primero por los `on_key`, desde el elemento enfocado hacia la raíz (sin foco, solo
la raíz). El primero que devuelva un valor verdadero la da por atendida. Si nadie la atiende, se
aplica el comportamiento por defecto:

| Tecla | Por defecto |
|---|---|
| Tab / Shift+Tab | Foco al siguiente / anterior. Dentro de una barrera `capture=True` (un modal), el foco no sale de ella. |
| Enter | Activa (`on_click`) el elemento enfocado. |
| Espacio | Activa el elemento enfocado al soltarla, con la animación de pulsado. Sin elemento activable, avanza una página. |
| ↑ ↓ ← → | Desplazan el `scroll` que contiene al foco o, sin foco, el que está bajo el puntero. |
| RePág / AvPág, Inicio / Fin | Desplazan una página / hasta el principio o el final. |

Para atajos globales, pon `on_key` en la raíz de la vista:

```python
def on_key(e: KeyEvent):
    if e.matches("mod+n"):  # Ctrl+N (Cmd+N en macOS)
        add_task()
        return True
    if e.matches("escape"):
        modal.set(None)
        return True
    return None  # el resto, comportamiento normal


def view():
    return column(on_key=on_key)[...]
```

### `KeyEvent`

| Atributo | Descripción |
|---|---|
| `key` | Nombre de la tecla: `"Enter"`, `"Tab"`, `"Escape"`, `"Space"`, `"Backspace"`, `"Delete"`, `"ArrowUp"`, `"Home"`, `"PageDown"`, `"F1"`… o el carácter (`"a"`, `"A"`, `"?"`). |
| `text` | Texto que produce la tecla (`"a"`, `" "`), o `None` (teclas de control, atajos con Ctrl/Alt/Cmd). |
| `ctrl`, `shift`, `alt`, `meta` | Modificadores pulsados. `meta` es Cmd en macOS y la tecla Windows en Windows. |
| `repeat` | `True` si es una repetición por mantener la tecla. |
| `matches(combo)` | `True` si la pulsación es exactamente esa combinación: `"ctrl+s"`, `"shift+tab"`, `"escape"`, `"mod+k"` (`mod` = Cmd en macOS, Ctrl en el resto). Las letras no distinguen mayúsculas, y en los símbolos que requieren Shift (`"?"`) no hace falta escribirlo. Una combinación mal escrita lanza `ValueError`. |

Alias aceptados en las combinaciones: `esc`, `return`, `del`, `up`/`down`/`left`/`right`, `pgup`/`pgdn`,
`plus`; y como modificadores `control`, `option`, `cmd`, `super` y `win`.

## Accesibilidad

Aurora publica lo que describe la vista en el API de accesibilidad del sistema (UIA en Windows,
NSAccessibility en macOS, AT-SPI en Linux) con [AccessKit](https://accesskit.dev): los lectores de
pantalla (Narrador, NVDA, VoiceOver, Orca) **ven el árbol** y sus acciones —activar, enfocar,
escribir un valor, ajustar un deslizador, desplazarse hasta un elemento— llegan a los mismos
manejadores que un clic o una tecla. Sin lector conectado el árbol ni se construye ni se actualiza.

- Los **componentes** declaran su semántica solos: `button` (nombre y activación), `checkbox` y
  `switch` (marcado), `radio` (grupo, posición y activo), `slider` (valor y rango), `text_input` /
  `textarea` (el valor real, incluido lo que se está escribiendo), `select` (valor, desplegado y
  opciones), `tabs`, `menu`, `dialog` (modal y título), `progress`, `toast` (región viva),
  `virtual_list` (posiciones) y `table` (cabeceras, filas y ordenación). `image` y `avatar` usan
  `alt`; sin él son decorativos.
- Las **primitivas** también cuentan: `text` es una etiqueta con su valor y cualquier elemento
  acepta las props de la tabla de [Primitivas](#primitivas). Una caja sin rol, sin nombre y sin
  contenido no se anuncia: el andamiaje de layout no ensucia el árbol.
- El **texto interno** de un control (la etiqueta de una casilla, el texto de un botón) no se
  anuncia dos veces: el nombre lo lleva el control.
- En los campos de texto, la acción «fijar valor» del lector escribe como si se tecleara (dispara
  `on_change` y respeta un valor controlado).
- Los **tests** pueden comprobar el árbol y simular acciones con `pilot.a11y_tree()` y
  `pilot.a11y_action(key, "click")` (ver [Pilot](#pilot-tests-de-interacción)).

```python
checkbox(acepto, "Acepto los términos", key="terms")  # el lector dice «Acepto los términos, casilla»

table(tasks, cols, key="t")  # la cabecera ordenada anuncia su orden y se activa con Enter

toast(message)  # un aviso: se anuncia solo al aparecer (región viva)
```

## Componentes

Construidos solo con primitivas: puedes leerlos en `python/aurora/components/` (un módulo por
familia) y usarlos como plantilla para los tuyos. Todos aceptan propiedades de estilo extra, que
sobrescriben las suyas.

### `button(label, on_click=None, *, variant="primary", key=None, **estilo)`

| `variant` | Aspecto |
|---|---|
| `"primary"` | Color de marca con brillo; acción principal. |
| `"soft"` | Superficie con borde; acciones secundarias. |
| `"ghost"` | Transparente hasta el hover; acciones terciarias. |

Por defecto: `padding=(10, 18)`, `radius="$md"`, contenido centrado, `font_weight=600`,
`press_scale=0.96`.

```python live
from aurora import button  # oculto

[button("Guardar"), button("Cancelar", variant="soft"), button("Más opciones", variant="ghost")]
```

### `card(**estilo)`

Columna con superficie, borde sutil, sombra y esquinas grandes. Por defecto: `bg="$surface"`,
`radius="$lg"`, `padding=20`, `gap=12`, `border_width=1`, `border_color="$border"`,
`shadow=(0, 10, 30, "$shadow")`.

```python live
from aurora import card, text  # oculto

card(width=320)[
    text("Copias de seguridad", size=16, weight=600),
    text("La última terminó hace 12 minutos sin errores.", color="$muted"),
]
```

### `badge(label, *, tone="accent")`

Píldora compacta de texto. `tone` es el nombre de un token de color del tema.

```python live
from aurora import badge  # oculto

[
    badge("beta"),
    badge("Estable", tone="success"),
    badge("Caído", tone="danger"),
    badge("v0.5", tone="primary"),
]
```

### `stat(label, value, delta=None, *, positive=True)`

Tarjeta de métrica: etiqueta, valor grande y variación opcional en verde (`positive=True`) o rojo.
Tiene `grow=1`, así que varias `stat` en una `row` se reparten el ancho.

```python live align=stretch
from aurora import row, stat  # oculto

row(gap=16)[
    stat("INGRESOS", "48.2k €", "+12%"),
    stat("DEVOLUCIONES", "2,1%", "+0,4", positive=False),
]
```

### `progress(value, *, max=1.0, color="$primary", **estilo)`

Barra de progreso: `value` va de 0 a `max` (por defecto, una fracción de 0 a 1) y se recorta a ese
rango. Al cambiar el valor, la barra crece hasta su nuevo sitio (con `App(motion=False)`, de
golpe). `color` admite un color del tema o un gradiente `(desde, hasta, ángulo)`; los `estilo` van
al carril (`height`, `width`…).

```python live
from aurora import column, progress  # oculto

column(gap=10, width=260)[
    progress(0.35),
    progress(0.7, color=("$primary", "$accent", 0)),
    progress(3, max=10, height=6, color="$success"),
]
```

### `spinner(*, size=8, gap=5, tone="$primary", key=None, **estilo)`

Indicador de carga: tres puntos que laten en cadena (`pulse`: un vaivén perpetuo de opacidad).
Mientras está visible el movimiento no se detiene — es lo que necesita un indicador — así que
retíralo cuando la carga termine. Con `App(motion=False)` queda fijo, a opacidad plena.

```python live
from aurora import App, box, spinner  # oculto

# El spinner no reposa nunca: para la captura, la app va con el movimiento apagado.
App(
    lambda: box(width=160, height=64, align="center", justify="center")[spinner()],
    size=(200, 100),
    motion=False,
).run()
```

### `skeleton(*, lines=1, width="100%", height=14, gap=8, **estilo)`

Marcador de carga: bloques con la forma del contenido que está por llegar. Con varias `lines`, la
última queda más corta, como el final de un párrafo. Late despacio (`pulse`) mientras está
visible. Los `estilo` van a cada bloque (`bg`, `radius`…).

```python live
from aurora import App, column, skeleton  # oculto

App(
    lambda: column(width=280, gap=14)[skeleton(lines=2, height=12), skeleton(height=12, width=100)],
    size=(280, 140),
    motion=False,
).run()
```

### `divider(*, vertical=False, color="$border", **estilo)`

Línea de 1 px. Horizontal por defecto (ocupa el ancho de su columna); con `vertical=True`, para
separar elementos de una `row` (ocupa su alto, o el `height` que le des).

### `avatar(name="", *, src=None, size=32, **estilo)`

Círculo de `size` px. Con `src` (ruta o `bytes`) muestra la imagen recortada (`fit="cover"`); sin
ella, las iniciales de `name` (hasta dos) sobre un color del tema que depende del nombre, así que
una persona siempre tiene el mismo color.

```python live
from aurora import avatar  # oculto

[avatar("Ada Lovelace"), avatar("Alan Turing", size=40), avatar("Grace Hopper", size=48)]
```

```python
avatar("Ada Lovelace", src="ada.jpg", size=40, tooltip="Ada · Admin")
```

### `checkbox(checked, label=None, *, on_change=None, key=None, **estilo)` y `switch(on, label=None, ...)`

Casilla de verificación e interruptor. Con un `Signal[bool]` se enlazan solos: un clic (o Enter /
Espacio con el foco) lo alterna. `on_change(valor)` se llama en cada cambio; con un `bool` fijo y
`on_change`, gestionas el valor tú. Toda la fila (control y etiqueta) es la zona de clic.

```python live
from aurora import DAYLIGHT, MIDNIGHT, Signal, checkbox, column, switch  # oculto

theme = Signal(MIDNIGHT)  # oculto
dark = Signal(True)
accepted = Signal(False)

column(gap=12)[
    switch(dark, "Tema oscuro", on_change=lambda on: theme.set(MIDNIGHT if on else DAYLIGHT)),
    checkbox(accepted, "Acepto las condiciones"),
]
```

### `radio(options, selected, *, key=None, **estilo)`

Grupo de botones de opción: uno activo a la vez. `options` son valores (o pares `(valor, etiqueta)`)
y `selected`, el `Signal` con el valor activo. Cada fila (círculo y etiqueta) se activa con clic,
Enter o Espacio y tiene la key `f"{key}-{valor}"`; con el foco en el grupo, las flechas eligen la
opción anterior o la siguiente. El punto interior entra encogiéndose.

```python live
from aurora import Signal, radio  # oculto

plan = Signal("pro")
radio([("free", "Gratis"), ("pro", "Pro"), ("team", "Equipo")], plan, key="plan")
```

### `tabs(options, selected, *, key=None, **estilo)`

Pestañas con indicador bajo la activa. `options` es una lista de valores o de pares
`(valor, etiqueta)` y `selected` el `Signal` con el valor activo. Con una pestaña enfocada, ← y →
cambian de pestaña. Cada pestaña tiene la key `f"{key}-{valor}"`.

```python live
from aurora import Signal, tabs  # oculto

page = Signal("resumen")
tabs([("resumen", "Resumen"), ("tablero", "Tablero"), ("equipo", "Equipo")], page, key="nav")
```

### `segmented(options, selected, *, width=220, key=None, **estilo)`

Selector segmentado: el pulgar se desliza hasta la opción activa. `options` son valores (o pares
`(valor, etiqueta)`) y `selected`, el `Signal` con el valor activo. Las ranuras miden todas lo
mismo, de ahí el `width` en píxeles (es lo que permite anclar el pulgar por fracción y que se
deslice). Cada opción tiene la key `f"{key}-{valor}"` y el pulgar la suya, `f"{key}-thumb"`. Los
`estilo` van al contenedor (`bg`…).

```python live
from aurora import Signal, segmented  # oculto

scope = Signal("Semana")
segmented(["Día", "Semana", "Mes"], scope, key="scope", width=280)
```

### `slider(value, *, min=0.0, max=1.0, width=180, on_change=None, key=None, **estilo)`

Deslizador: arrastra el pulgar para cambiar `value` (un `Signal[float]`), recortado al rango
`min`…`max`. `width` fija el ancho en píxeles (el arrastre se calcula con él: no lo pongas en `%`).
`on_change(valor)` se llama en cada paso del arrastre. El relleno y el pulgar siguen el valor con
la animación común; con `App(motion=False)`, al instante.

```python live
from aurora import Signal, slider  # oculto

volume = Signal(0.6)
slider(volume, key="volume", width=240)
```

### `pages(current, views, *, key="pages", **estilo)`

Una vista por valor de `current` (un `Signal`), con transición al cambiar: la página nueva entra
fundiéndose y la anterior se va. `views` asocia cada valor con una función que devuelve su
contenido; un valor sin vista lanza `ValueError`. Es el compañero natural de `tabs`: comparten el
`Signal`, cambiar de pestaña cambia de página.

Cada página es su propio `scroll` (su key es `f"{key}-{valor}"`) que ocupa el espacio libre, así
que no hace falta darle `height`; los `estilo` van a él (`padding`, `gap`…). Al volver a una
página empieza arriba.

```python live
from aurora import Signal, column, pages, text  # oculto

current = Signal("uno")  # oculto

pages(
    current,
    {
        "uno": lambda: column(gap=6)[text("Página uno"), text("Su contenido", color="$muted")],
        "dos": lambda: column(gap=6)[text("Página dos"), text("Otro contenido", color="$muted")],
    },
    key="demo",
    padding=8,
    height=90,
)
```

### `splitter(first, second, *, size=240, direction="row", min_sizes=(80, 80), step=16, on_change=None, key=None, **estilo)` { #splitter }

Dos paneles con un separador entre ellos que se arrastra para repartir el espacio: una barra
lateral y el contenido, una lista y su detalle, un editor y su consola. Con `direction="row"` los
paneles van uno al lado del otro y el separador cambia anchos; con `"column"`, uno encima del otro.

`size` es el tamaño del primer panel en píxeles; el segundo ocupa el resto. Con un `Signal[float]`
queda enlazado —arrastrar lo cambia y asignarlo mueve el separador—; con un número es el tamaño
inicial y el estado vive en la `key`, que entonces es obligatoria. `min_sizes` son los mínimos de
cada panel: el separador no los rebasa, y si la ventana encoge el primer panel cede hasta su
mínimo sin cambiar `size`, así que vuelve a su tamaño al crecer de nuevo. `on_change(tamaño)` se
llama en cada cambio.

El separador es enfocable: las flechas lo mueven `step` píxeles (←/→ en horizontal, ↑/↓ en
vertical) e Inicio/Fin lo llevan a los extremos. Para los lectores de pantalla es un
`"separator"` con su orientación y el tamaño como valor, que se ajusta con las acciones
Incrementar/Decrementar. Cada panel es una columna que recorta lo que se sale: dale `grow=1` a su
contenido (un `scroll`, por ejemplo) para que lo rellene. Las keys son `f"{key}-first"`,
`f"{key}-handle"` y `f"{key}-second"`; los `estilo` van al contenedor, que crece (`grow=1`).

```python live
from aurora import App, Signal, column, scroll, splitter, text

lateral = Signal(150.0)


def view():
    carpetas = scroll(padding=12, gap=8, bg="$surface")[
        [text(nombre, size=13) for nombre in ("Entrada", "Enviados", "Borradores", "Archivo")]
    ]
    detalle = scroll(padding=12)[text("Selecciona un mensaje", color="$muted")]
    return column(padding=12)[
        splitter(
            carpetas,
            detalle,
            size=lateral,
            min_sizes=(110, 160),
            radius="$md",
            border_width=1,
            border_color="$border",
            overflow="hidden",
        )
    ]


App(view, size=(420, 220)).run()
```

Para tres paneles o más, anida un `splitter` dentro de otro. El tamaño del contenedor lo mide el
evento [`on_resize`](#primitivas), que sirve también para adaptar cualquier vista al espacio que
le toca.

### `select(value, options, *, placeholder="Elegir…", key=None, **estilo)`

Desplegable. `value` es un `Signal` y `options`, valores o pares `(valor, etiqueta)`. La lista se
abre por encima de todo (`layer="overlay"`), con scroll si es larga, y se cierra al elegir, al hacer
clic fuera, con Esc o con Enter. Con el desplegable enfocado, ↑ y ↓ cambian el valor sin abrirlo.
Ancho mínimo de 160 px; los estilos extra (`width`, `grow`…) se aplican al contenedor. Las opciones
tienen la key `f"{key}-opt-{índice}"`.

```python live
from aurora import Signal, select  # oculto

lang = Signal("es")
select(lang, [("es", "Español"), ("en", "English")], key="lang", width=220)
```

### `combobox(value, options, *, placeholder="Buscar…", empty="Sin resultados", on_change=None, key=None, **estilo)`

Como `select`, pero se escribe para buscar: la lista se abre al escribir (o con ↓, o con la flecha)
y muestra las opciones cuya etiqueta contiene el texto, sin distinguir mayúsculas ni tildes
(«av» encuentra «Ávila»). ↑/↓ recorren las coincidencias, Enter elige la resaltada y Esc cierra sin
cambiar nada; al cerrar, el campo vuelve a mostrar la opción elegida. `empty` es lo que se lee
cuando nada coincide. `on_change(valor)` se llama al elegir. El campo tiene la key `f"{key}-field"`
y las opciones `f"{key}-opt-{índice}"`, con el índice en `options` (no en la lista filtrada).
Útil cuando hay demasiadas opciones para un `select`.

```python live
from aurora import App, Signal, column, combobox
from aurora.components import _state  # oculto

_state._OPEN["ciudad"] = Signal(True)  # oculto
_state._QUERIES["ciudad"] = Signal("al")  # oculto
ciudades = ["Albacete", "Alicante", "Ávila", "Barcelona", "Málaga", "Valencia", "Valladolid"]
ciudad = Signal("Valencia")


def view():
    return column(padding=20)[combobox(ciudad, ciudades, key="ciudad", width=260)]


App(view, size=(420, 300)).run()
```

### `date_picker(value, *, min=None, max=None, placeholder="Elegir fecha", format=..., first_weekday=0, on_change=None, key=None, **estilo)`

Selector de fecha: un desplegable con el calendario del mes. `value` es un `Signal` con un
`datetime.date` (o `None` sin elegir). Se abre en el mes de la fecha elegida; las flechas de la
cabecera cambian de mes y un clic en un día lo elige y cierra. Las fechas fuera de `[min, max]` se
ven atenuadas y no se pueden elegir (ni navegar a meses fuera del rango). El día de hoy va marcado
y «Hoy» lo elige.

Con el calendario abierto, ←/→ mueven un día, ↑/↓ una semana y RePág/AvPág un mes (el mes visible
sigue al valor); Enter o Esc lo cierran. `format` recibe la fecha y devuelve el texto del campo
(por defecto `19 oct 2026`), y `first_weekday` es el primer día de la semana (0 = lunes,
6 = domingo). Los días tienen la key `f"{key}-day-{fecha.isoformat()}"` y se anuncian completos a
los lectores de pantalla («lunes, 19 de octubre de 2026»).

```python live
from datetime import date

from aurora import App, Signal, column, date_picker
from aurora.components import _state  # oculto

_state._OPEN["entrega"] = Signal(True)  # oculto
entrega = Signal(date(2026, 10, 19))


def view():
    return column(padding=20)[date_picker(entrega, min=date(2026, 10, 5), key="entrega", width=220)]


App(view, size=(340, 440)).run()
```

### `time_picker(value, *, step=15, min=None, max=None, hour12=False, placeholder="Elegir hora", format=None, on_change=None, key=None, **estilo)` { #time_picker }

Selector de hora, hermano de `date_picker`: un desplegable con las horas del día cada `step`
minutos. `value` es un `Signal` con un `datetime.time` (o `None` sin elegir). La lista va de `min`
a `max` (por defecto, el día entero) y se abre con la hora elegida a la vista; una hora que no cae
en un paso (`10:07`) se muestra tal cual en el campo. Con `hour12=True` se escribe `2:30 p. m.` en
vez de `14:30`, y `format` (una función de `time` a texto) lo decide a medida.

Con la lista abierta, ↑/↓ pasan a la hora anterior o siguiente, Inicio/Fin a la primera y la
última, y Enter o Esc la cierran. Es un `"combobox"` con un `"listbox"` de `"option"`s; las
opciones tienen la key `f"{key}-{HH:MM}"`.

```python live
from datetime import time

from aurora import App, Signal, column, time_picker
from aurora.components import _state  # oculto

_state._OPEN["cita"] = Signal(True)  # oculto
cita = Signal(time(10, 30))


def view():
    return column(padding=20)[
        time_picker(cita, step=30, min=time(8, 0), max=time(20, 0), key="cita", width=200)
    ]


App(view, size=(300, 330)).run()
```

### `color_picker(value, *, palette=..., custom=True, on_change=None, key=None, **estilo)` { #color_picker }

Selector de color: el campo muestra una muestra y el código, y abre un panel con un **cuadro de
saturación y brillo**, una **franja de tono**, la **paleta** de muestras rápidas y un campo
**hexadecimal**. `value` es un `Signal[str]` con el color en la forma `#RRGGBB`; al escribir se
aceptan `#RGB`, sin `#` y en minúsculas, y el color se asigna en cuanto el texto es válido.

`palette` cambia las muestras (por defecto, una gama que se ve bien en claro y en oscuro) y
`custom=False` quita el cuadro y la franja para elegir solo entre ellas. El cuadro y la franja se
arrastran o, enfocados, se manejan con las flechas (en el cuadro, ←/→ cambian la saturación y ↑/↓
el brillo); el tono se conserva aunque el color pase por un gris. Esc cierra el panel y
`on_change(color)` se llama con cada color nuevo. Para los lectores de pantalla, el cuadro y la
franja son `"slider"`s y la paleta un grupo de `"radio"`s (keys `f"{key}-swatch-{índice}"`).

```python live
from aurora import App, Signal, color_picker, column
from aurora.components import _state  # oculto

_state._OPEN["acento"] = Signal(True)  # oculto
acento = Signal("#7C5CFF")


def view():
    return column(padding=20)[color_picker(acento, key="acento", width=200)]


App(view, size=(300, 420)).run()
```

### `number_input(value, *, min=None, max=None, step=1, decimals=None, on_change=None, key=None, **estilo)`

Campo numérico: se escribe el número o se ajusta con ↑/↓ y con las flechas de la derecha (que se
atenúan en los límites). `value` se recorta a `[min, max]`. Con `step` entero y un valor entero el
campo trabaja con `int`; si no, con `float` redondeado a `decimals` (por defecto, los decimales de
`step`: `0.25` → 2). La coma vale como separador decimal.

Mientras se escribe, cada número válido y dentro del rango se asigna al momento; un texto a medias
(`"-"`, `"1,"`) o fuera del rango espera, y al salir del campo o pulsar Enter se recorta al rango o
vuelve al último valor válido. `on_change(valor)` se llama con cada valor nuevo. Ancho por defecto
de 140 px; el campo tiene la key `f"{key}-field"` y es un `spinbutton` para los lectores.

```python live
from aurora import Signal, number_input, row  # oculto

cantidad = Signal(3)
precio = Signal(12.5)
row(gap=12)[  # oculto
    number_input(cantidad, min=1, max=99, key="cantidad"),
    number_input(precio, step=0.5, key="precio"),
]  # oculto
```

### `sortable(items, item, *, key, group=None, ident=None, item_label=str, on_move=None, direction="column", gap=8, empty=None, **estilo)` { #sortable }

Lista cuyos elementos se reordenan arrastrándolos, o con el teclado. `item(valor)` construye
cada uno. Al soltar uno en otra posición se llama a `on_move(evento)` con un
[`MoveEvent`](#moveevent): la lista no cambia sola, la cambias tú, y `evento.apply(...)` hace el
movimiento sobre tus datos. Las `sortable` con el mismo `group` forman un **tablero**: los
elementos pasan de una a otra, y se llama al `on_move` de la de destino (o, si no tiene, al de la
de origen).

```python live size=480x220 align=stretch
from aurora import App, Signal, box, column, row, sortable, text

tablero = Signal({"Pendiente": ["Diseño", "Docs"], "En curso": ["API"], "Hecho": []})


def tarjeta(titulo):
    return box(padding=10, radius="$sm", bg="$surface", border_width=1, border_color="$border")[text(titulo)]


def view():
    return row(gap=12, padding=16, align="start")[
        [
            column(gap=8, grow=1, width=0)[
                text(nombre, size=12, weight=700, color="$muted"),
                sortable(
                    tareas,
                    tarjeta,
                    key=nombre,
                    group="tablero",
                    label=nombre,
                    empty=text("Suelta aquí", size=12, color="$muted", padding=12),
                    on_move=lambda e: tablero.set(e.apply(tablero())),
                ),
            ]
            for nombre, tareas in tablero().items()
        ]
    ]


App(view, size=(480, 220)).run()
```

- **Puntero**: el arrastre empieza al mover 4 px con el botón pulsado, así que un clic no
  arrastra y los botones de dentro de un elemento siguen funcionando. El elemento se levanta y
  sigue al puntero por encima de todo (con sombra), su hueco queda libre y una línea del color
  `$primary` marca dónde caerá; una lista vacía se resalta entera. Soltar fuera de las listas
  del grupo lo cancela.
- **Teclado**: con un elemento enfocado (Tab), Espacio o Enter lo coge; las flechas del eje de
  la lista lo mueven, las del otro eje lo pasan a la lista anterior o siguiente del grupo (en
  el orden en que se construyen), Espacio o Enter lo sueltan y Esc cancela. El foco sigue al
  elemento de una lista a otra.
- **Lectores de pantalla**: es una `"list"` de `"listitem"`s con su posición y la descripción
  «Espacio para mover»; el elemento cogido queda `selected`, y cada paso se anuncia en una
  región viva (`"assertive"`): ««Docs», posición 2 de 3 en «Pendiente»», «soltado en…»,
  «Cancelado…». Dale a cada lista un `label`: es el nombre que dicen los anuncios.
- `ident(valor)` identifica cada elemento (por defecto, el propio valor, que debe ser hashable);
  su key es `f"{grupo}:{identidad}"`, para hacer clic, enfocarlo o arrastrarlo en tests
  (`pilot.drag_to("tablero:Docs", "En curso")`). `item_label(valor)` es su nombre accesible y
  el de los anuncios (por defecto, `str`).
- `direction="row"` la pone en fila; `gap` separa los elementos; `empty` se muestra dentro de la
  lista cuando está vacía (sigue siendo zona de soltar). El resto de argumentos son estilo del
  contenedor (por defecto, `min_height=48`).

Lo hace sin código nativo propio: el núcleo solo dice, en cada [`DragEvent`](#dragevent), sobre
qué zona (`drop_target=True`) está el puntero y en qué posición caería. Con esas dos piezas se
puede construir otro tipo de arrastre (soltar en una papelera, en una carpeta de un `tree`…).

#### `MoveEvent`

| Atributo | Descripción |
|---|---|
| `item` | El valor movido. |
| `source`, `source_index` | La key de la lista de origen y dónde estaba en ella. |
| `target`, `index` | La key de la lista de destino (la misma si se reordena) y dónde queda en ella, ya quitado de la de origen. |
| `apply(datos)` | Una copia de tus datos con el movimiento hecho: con una lista (reordenar una sola `sortable`), la lista nueva; con un dict de key de lista → elementos (un tablero), el dict nuevo. No cambia los originales. |

### `virtual_list(count, item, *, item_height=None, estimated_height=40, key, gap=0, overscan=4, stick_to_end=False, **estilo)` { #virtual_list }

Lista desplazable de `count` filas que **solo construye las visibles**: con 100 000 filas, cada
reconstrucción crea unas pocas decenas y desplazarse cuesta lo mismo que con 20. Las filas pueden
medir todas lo mismo (`item_height`) o cada una lo suyo.

```python
@component
def fila(i: int, seleccionada: bool):
    return row(grow=1, padding=(0, 12), align="center", bg="$surface" if seleccionada else None)[
        text(tareas()[i].titulo)
    ]


virtual_list(len(tareas()), lambda i: fila(i, i == elegida()), item_height=36, key="tareas")
```

- `item(i)` devuelve la fila `i`. Cada fila ocupa un hueco de todo el ancho y `item_height` de alto
  (más `gap` entre filas): dale `grow=1` a su raíz para que lo rellene. Todas las filas miden lo
  mismo; así la lista conoce su alto total sin construirlas.
- Se comporta como un [`scroll`](#scroll-axisy-estilo) vertical (los `**estilo` van a él) y la
  `key`, obligatoria, guarda su posición y su zona visible.
- Al desplazarse solo se reconstruye cuando cambia el rango de filas visibles, en el mismo frame.
  `overscan` filas de más por cada lado cubren el desplazamiento entre medias.
- Con filas `@component`, las que siguen visibles no se reconstruyen.
- Solo las filas construidas existen en el árbol: Tab recorre las visibles, y `Pilot.rect` de una
  fila fuera de la zona visible devuelve `None`.

#### Filas de alto variable

Sin `item_height`, cada fila mide lo que pida su contenido: mensajes de un chat, tarjetas con
textos de distinto largo. Las que aún no se han construido se suponen de `estimated_height`; al
construirse, el layout las mide y la lista corrige su alto total. Lo que se está viendo **no
salta** al corregirse lo de encima (la lista usa `scroll_anchor`), y si se estaba al final se sigue
viendo el final.

```python live size=360x260 align=stretch
from aurora import App, Signal, box, column, text, virtual_list

mensajes = Signal(
    [
        "Hola",
        "¿Has visto la nueva versión? Las listas virtuales ya admiten filas de alto variable.",
        "Sí 🙂",
        "Y si estás al final, los mensajes nuevos se siguen viendo sin tocar nada.",
    ]
    * 50
)


def burbuja(i):
    mio = i % 2 == 1
    return box(padding=(4, 12), align="end" if mio else "start")[
        box(padding=(8, 12), radius=14, max_width=240, bg="$primary" if mio else "$surface")[
            text(mensajes()[i], size=13, color="#FFFFFF" if mio else "$text")
        ]
    ]


def view():
    return column(padding=(8, 0))[
        virtual_list(len(mensajes()), burbuja, key="chat", estimated_height=48, stick_to_end=True),
    ]


App(view, size=(360, 260)).run()
```

- Los altos medidos se guardan por índice en la `key`: si cambia el contenido de una fila
  visible, se vuelve a medir sola; una que no se ve conserva su último alto hasta que vuelva a
  construirse.
- Cuanto más se acerque `estimated_height` a la media real, más fiel es la barra de
  desplazamiento antes de haber visto las filas. Sin `item_height`, la fila no ocupa un hueco
  fijo: su raíz no necesita `grow=1`.
- Medir una fila nueva cuesta O(log n) y saber qué filas se ven, O(log² n): con 100 000 filas
  sigue construyendo solo las visibles.
- `stick_to_end=True` (también con `item_height`) empieza al final y, mientras se esté al final,
  lo sigue cuando llegan filas nuevas: un chat o un registro. Si el usuario sube a leer, no se
  mueve.

### `tree(roots, children, *, key, label=str, ident=None, expanded=None, selected=None, icon=None, on_select=None, on_activate=None, item_height=30, indent=18, overscan=4, **estilo)` { #tree }

Árbol expandible para jerarquías: carpetas y archivos, categorías, el esquema de un documento.
`roots` son los nodos de primer nivel y `children(nodo)` devuelve los hijos de cada uno (vacío en
las hojas); solo se pide para los nodos visibles, así que puede cargarlos bajo demanda. Los nodos
son cualquier objeto: `label(nodo)` da su texto, `icon(nodo)` (opcional) un elemento delante de él
e `ident(nodo)` su identidad, única y estable; por defecto es la tupla de etiquetas desde la raíz
(`("src", "main.py")`).

```python live
from aurora import App, Signal, column, tree

archivos = [
    ("src", [("app.py", []), ("ui", [("tree.py", []), ("splitter.py", [])])]),
    ("docs", [("guía.md", [])]),
    ("README.md", []),
]
abiertos = Signal({("src",), ("src", "ui")})
elegido = Signal(("src", "ui", "tree.py"))


def view():
    return column(padding=12)[
        tree(
            archivos,
            lambda nodo: nodo[1],
            label=lambda nodo: nodo[0],
            expanded=abiertos,
            selected=elegido,
            key="archivos",
        )
    ]


App(view, size=(300, 230)).run()
```

- `expanded` es un `Signal` con el **conjunto** de identidades desplegadas y `selected` uno con la
  del nodo elegido (o `None`): léelos o asígnalos desde fuera (`abiertos.set(abiertos() |
  {("docs",)})`). Sin ellos, el estado vive en la `key`, que siempre es obligatoria.
- Un clic elige la fila y el triángulo la despliega o la pliega. `on_select(nodo)` se llama al
  elegir y `on_activate(nodo)` al pulsar Enter.
- Con el árbol enfocado, ↑/↓ recorren las filas visibles, → despliega (o baja al primer hijo),
  ← pliega (o sube al padre), Inicio/Fin van a la primera y a la última fila, y Enter llama a
  `on_activate` (sin él, despliega o pliega). La fila elegida siempre queda a la vista.
- Se apoya en `virtual_list`: solo construye las filas visibles, todas de `item_height`, así que
  un árbol con decenas de miles de nodos desplegados cuesta lo mismo que uno pequeño. Como ella,
  ocupa el espacio libre; dale `height` o `max_height` para acotarlo. `indent` es la sangría por
  nivel.
- Para los lectores de pantalla es un `"tree"` de `"treeitem"`s con su nivel, su posición entre
  hermanos («2 de 5») y si están desplegados. Las filas tienen la key `f"{key}-{identidad}"` (una
  tupla se une con `/`: `"archivos-src/app.py"`).

### `table(rows, columns, *, key, sort=None, widths=None, on_row_click=None, row_height=36, header_height=40, striped=True, empty="Sin datos", overscan=4, **estilo)`

Tabla de datos con cabecera fija, **ordenación**, **columnas redimensionables** y filas
**virtualizadas**: solo se construyen las visibles, así que con 100 000 filas desplazarse cuesta
lo mismo que con 20.

```python live align=stretch
# oculto: inicio
from dataclasses import dataclass

from aurora import Signal, badge


@dataclass(frozen=True)
class Pedido:
    id: int
    cliente: str
    total: float
    estado: str


pedidos = Signal(
    (
        Pedido(1041, "Lucía Fernández", 1280.5, "pagado"),
        Pedido(1042, "Marco Rossi", 89.9, "pendiente"),
        Pedido(1043, "Aiko Tanaka", 342.0, "pagado"),
        Pedido(1044, "Omar Haddad", 15.75, "devuelto"),
    )
)
abierto = Signal(None)
# oculto: fin
from aurora import Column, table

table(
    pedidos(),
    [
        Column("id", "Nº", width=80, align="end"),
        Column("cliente", "Cliente", width=220),
        Column("total", "Total", align="end", format=lambda v: f"{v:,.2f} €"),
        Column("estado", "Estado", cell=lambda p: badge(p.estado), sortable=False),
    ],
    key="pedidos",
    on_row_click=lambda p: abierto.set(p.id),
    height=200,  # oculto
)
```

- `rows` es cualquier secuencia: dicts, tuplas, dataclasses u otros objetos. `columns` son
  objetos `Column` o simplemente keys (`["id", "nombre"]`).
- **Ordenar:** pulsar una cabecera ordena por esa columna, ascendente → descendente → orden
  original. Los textos se comparan sin distinguir mayúsculas, los vacíos (`None`) van siempre al
  final y los empates conservan el orden original. El orden se calcula una vez y se memoriza
  mientras `rows` sea el mismo objeto y no cambie de longitud: si cambian los datos, pasa una
  secuencia nueva en vez de modificarla en su sitio.
- **Redimensionar:** arrastrar el borde derecho de una cabecera cambia el ancho de su columna (sin
  bajar de `min_width`). Si las columnas no caben, la tabla se desplaza en horizontal.
- El orden y los anchos se guardan por `key`. Para leerlos o fijarlos desde fuera, pasa tus
  `Signal`: `sort` con `(key_de_columna, descendente)` o `None`, y `widths` con
  `{key_de_columna: ancho}` (las que falten usan `Column.width`).
- `on_row_click(fila)` hace las filas pulsables. `striped` alterna el fondo de las filas y `empty`
  es el texto que se muestra sin filas.
- Sin `height` ni `max_height`, ocupa el espacio libre (`grow=1`), como un `scroll`.
- En los tests, las cabeceras tienen key `"{key}/h/{columna}"`, los bordes
  `"{key}/resize/{columna}"`, las filas `"{key}/row/{índice en rows}"` y el cuerpo desplazable
  `"{key}/body"`.

#### `Column(key, title=None, *, width=160, min_width=48, align="start", value=None, format=None, cell=None, sortable=True, resizable=True)`

| Campo | Descripción |
|---|---|
| `key` | Identifica la columna. Sin `value`, el valor de cada celda es `fila[key]` en un dict, `getattr(fila, key)` en un objeto o la posición de la columna en una tupla o lista. |
| `title` | Texto de la cabecera. Por defecto, la `key`. |
| `width` / `min_width` | Ancho inicial y mínimo al redimensionar, en píxeles. |
| `align` | `"start"`, `"center"` o `"end"` (números). |
| `value` | `value(fila)`: valor de la celda, que es lo que se ordena. |
| `format` | `format(valor)`: texto que se muestra. Por defecto, `str(valor)` (`None` se muestra vacío). |
| `cell` | `cell(fila)`: elemento que sustituye al texto (badges, avatares, botones). La ordenación sigue usando el valor. |
| `sortable` / `resizable` | Si la cabecera ordena al pulsarla / si su borde se puede arrastrar. |

### `title_bar(title=None, *, icon=None, actions=None, window=None, controls=True, height=36, key="title-bar", **estilo)` { #title_bar }

Barra de título para una ventana [sin marco](#ventanas-sin-marco): toda ella mueve la ventana
(`window_drag="move"`, doble clic para maximizar) y lleva los botones de minimizar, maximizar o
restaurar, y cerrar (este pasa por `on_close`). `icon` va delante del título y `actions` (un
elemento o una lista) antes de los botones; sus clics no mueven la ventana. Actúa sobre la ventana
cuya vista se construye ([`current_window()`](#current_window)) o sobre `window`.

Los botones siguen al sistema: en Windows y Linux, a la derecha (cerrar se vuelve rojo al pasar
por encima); en macOS, los tres círculos a la izquierda. `controls="windows"` o
`controls="macos"` fija un estilo; `controls=False` los quita. Por defecto, fondo `$surface` y
36 px de alto; las keys de los botones son `f"{key}-minimize"`, `-maximize` (o `-restore` si
está maximizada) y `-close`, y para los lectores de pantalla son botones con su nombre.

```python live size=480x120
from aurora import App, column, text, title_bar


def view():
    return column(grow=1)[
        title_bar("Informe.md — Editor", icon=text("◆", color="$primary"), controls="windows"),
    ]


App(view, size=(480, 120), decorations=False).run()
```

### `tooltip(child, tip)`

Muestra `tip` en una burbuja al dejar el puntero **medio segundo** sobre `child`. Aparece debajo
(o encima, si no cabe), sin salirse de la ventana, se oculta al hacer clic o pulsar una tecla, y
no intercepta el ratón. Es lo mismo que pasar `tooltip="..."` a cualquier elemento:

```python
tooltip(button("Guardar", save), "Ctrl+S")
image("info.svg", width=16, tooltip="Se actualiza cada hora")
```

La burbuja usa los colores heredables `tooltip_bg` y `tooltip_color`, que por defecto invierten el
tema (`$text` sobre `$background`), así destaca en claro y en oscuro.

### `popover(trigger, content, *, open=None, placement="bottom-start", offset=6, label=None, on_close=None, key=None, **estilo)` { #popover }

Contenido flotante anclado a un elemento: pulsar `trigger` abre y cierra un panel con `content`
(un formulario corto, filtros, detalles…). El panel se pinta por encima del resto
(`layer="overlay"`) en el lado de `placement`, a `offset` píxeles del disparador: `"top"`,
`"bottom"`, `"left"` o `"right"`, opcionalmente con la alineación (`"bottom-start"`,
`"right-center"`, `"top-end"`…). Si en ese lado no cabe se **vuelca** al opuesto, y en el otro eje
se desplaza lo justo para no salirse de la ventana. Se cierra con Esc, al hacer clic fuera o
pulsando otra vez el disparador, y entonces llama a `on_close()`.

El estado vive en `open` (un `Signal[bool]`, para abrirlo o cerrarlo desde fuera) o, sin él, en la
`key`: hace falta una de las dos (`ValueError` si no). Para los lectores de pantalla el panel es un
`"dialog"` no modal con nombre `label`, toma el foco al abrirse (salvo que el contenido traiga un
`autofocus`) y el disparador anuncia si está desplegado (`expanded`). Los `estilo` van al panel
(`width`, `padding`, `gap`…); el panel tiene la key `f"{key}-panel"`.

```python live
from aurora import App, Signal, button, column, popover, row, switch, text

filtros = Signal(True)  # oculto
avisos, archivados = Signal(True), Signal(False)


def view():
    contenido = column(gap=10)[
        text("Mostrar", size=12, weight=600, color="$muted"),
        switch(avisos, "Avisos"),
        switch(archivados, "Archivados"),
    ]
    return row(padding=20)[
        popover(button("Filtros", variant="soft"), contenido, open=filtros, label="Filtros", width=200)
    ]


App(view, size=(320, 200)).run()
```

La colocación es la propiedad de estilo [`placement`](#apariencia) (con `offset`), que sirve a
cualquier elemento con `layer="overlay"`: se ancla a su **hermano anterior** que ocupa sitio en el
flujo (en `popover`, el disparador) o, si no lo hay, a su contenedor. La usan también `menu`, `select`, `combobox` y `date_picker`,
así que todos se abren hacia arriba cuando no caben debajo.

### `dialog(open, content, *, title=None, on_close=None, width=420, key=None, **estilo)`

Diálogo modal: fondo oscurecido y tarjeta centrada con `content`. Con un `Signal[bool]` en `open`
se cierra solo — el clic fuera y Esc lo ponen a `False` —; `on_close` se llama en cada cierre, útil
si `open` es un booleano fijo o quieres cerrar un modal de varios estados
(`on_close=lambda: modal.set(None)`). `title` añade un encabezado; los `estilo` van a la tarjeta
(`padding`, `shadow`…).

La tarjeta toma el foco al abrirse y lo atrapa (Tab no sale de ella), salvo que el contenido traiga
un `autofocus`, que gana. Entra con un zoom suave y sale fundiéndose. Devuelve `None` mientras está
cerrado: colócalo como **último hijo de la raíz** (o con `layer="overlay"`).

```python live
from aurora import Signal, box, button, column, dialog, row, text  # oculto

open_ = Signal(True)  # oculto

box(width=380, height=260, bg="$background")[
    dialog(
        open_,
        column(gap=14)[
            text("¿Eliminar la tarea «Refactor»?"),
            row(gap=8, justify="end")[
                button("Cancelar", lambda: None, variant="soft"),
                button("Eliminar", lambda: None),
            ],
        ],
        title="Confirmación",
        width=300,
    )
]
```

### `toast(message, *, on_close=None, tone="$accent", key=None, **estilo)`

Aviso flotante abajo a la derecha. `message` puede ser un `Signal[str | None]`: se muestra si no es
`None` y un clic lo descarta (el Signal pasa a `None`). `on_close` se llama en cada cierre; `tone`
es el color del punto de acento y los `estilo` van al aviso (`right`, `bottom`, `max_width`…). Entra
deslizándose desde abajo y sale fundiéndose. Devuelve `None` mientras no hay mensaje: colócalo como
**último hijo de la raíz**. Para que se vaya solo, programa el Signal con la app
(`app.spawn(asyncio.sleep(3))` y ponerlo a `None` al terminar).

```python live
from aurora import box, column, text, toast  # oculto

box(width=380, height=200, bg="$background", padding=18)[
    column(gap=6)[text("Ajustes guardados", weight=600), text("Hace un momento", color="$muted", size=12)],
    toast("Cambios guardados", tone="$success"),
]
```

### `menu(trigger, items, *, key, drop=None, placement="bottom-start", **estilo)`

Menú de acciones: `trigger` es el elemento que se pulsa (normalmente un botón o un "⋯") y `items`
la lista de opciones, `(etiqueta, on_click)` o `(etiqueta, on_click, estilo)` — el estilo extra va
al texto, para una acción peligrosa: `{"color": "$danger"}`. La lista se pinta por encima
(`layer="overlay"`), entra deslizándose y se cierra al elegir, al hacer clic fuera o con Esc.
Se abre debajo del disparador (o en el lado de `placement`, como un [`popover`](#popover)) y se
vuelca encima si no cabe; `drop` lo fija en cambio a esa distancia del borde superior del
disparador. `key` (obligatoria, como en `virtual_list`) guarda el estado de abierto: las opciones
tienen la key `f"{key}-item-{índice}"`.

```python
menu(
    button("Acciones", variant="soft"),
    [
        ("Editar", edit),
        ("Duplicar", duplicate),
        ("Eliminar", remove, {"color": "$danger"}),
    ],
    key="acciones",
)
```

### `accordion(sections, open, *, key=None, **estilo)`

Acordeón: cada sección se despliega al pulsar su cabecera. `sections` son triples
`(valor, título, contenido)` y `open`, el `Signal` con la sección desplegada (`None` con todas
plegadas; pulsar la cabecera abierta la pliega). El contenido se despliega con la altura animada y
`overflow="hidden"`, **se queda montado** al plegarse (conserva su estado y no recibe clics
mientras está oculto). Cada sección tiene la key `f"{key}-{valor}"`.

```python live
from aurora import Signal, accordion, text  # oculto

section = Signal("uno")  # oculto

accordion(
    [
        ("uno", "Cómo funciona", text("El contenido se recorta y se despliega animado.")),
        ("dos", "Atajos", text("Pulsa cualquier cabecera para abrir o cerrar su sección.")),
    ],
    section,
    key="demo",
    width=380,
)
```

### `field(control, *, label=None, hint=None, error=None, key=None, **estilo)`

Campo de formulario: etiqueta encima, el control y, debajo, un mensaje de ayuda o de error. `error`
sustituye a `hint` en color de peligro (`$danger`): pásalo con el texto del problema y quítalo
cuando el valor sea válido. Los `estilo` van a la columna (`gap`, `width`, `grow`…). La etiqueta
es también el nombre accesible del control (si no trae uno), así que el lector anuncia «Correo,
campo de texto» y no la etiqueta suelta.

```python live
from aurora import Signal, field, text_input  # oculto

email = Signal("")
field(text_input(email, placeholder="tu@correo.com", width=240), label="Correo", hint="No lo compartimos")
```

### `text_input(value, *, placeholder="", on_change=None, on_submit=None, key=None, **estilo)`

Campo de texto de una línea. `value` es normalmente un `Signal[str]`, y entonces queda **enlazado
en los dos sentidos**: lo que se escribe actualiza el Signal y lo que asignes al Signal aparece en
el campo (por ejemplo, vaciarlo al enviar).

```python live
from aurora import Signal, text_input  # oculto

query = Signal("")
text_input(query, placeholder="Buscar…", on_submit=lambda q: search(q))
```

| Parámetro | Descripción |
|---|---|
| `value` | `Signal[str]` (enlazado), o un `str`/callable con `on_change` para gestionar el valor tú. Sin `on_change`, un valor fijo no cambia al escribir. |
| `placeholder` | Texto atenuado que se muestra con el campo vacío. Se toma literalmente (un `"$"` inicial no es un token). |
| `on_change` | `fn(texto)` en cada cambio (después de actualizar el Signal). |
| `on_submit` | `fn(texto)` al pulsar Enter. |

Por defecto: `bg="$surface"`, borde de 1 px `$border`, `radius="$md"`, `padding=(9, 12)` y
200 px de ancho si su contenedor no le da otro (con `align="stretch"`, ocupa el ancho disponible).
Un campo con foco siempre muestra el anillo de foco, también tras un clic.

**Edición:** escribir (incluido texto compuesto con IME), Retroceso/Supr (con Ctrl, o Alt en macOS,
por palabras), flechas (con Mayús seleccionan; con Ctrl/Alt saltan palabras), Inicio/Fin,
Ctrl+A, Ctrl+C/X/V, Ctrl+Z y Ctrl+Mayús+Z o Ctrl+Y (Cmd en macOS). Con el ratón: clic coloca el
cursor (Mayús+clic amplía la selección), arrastrar selecciona, doble clic selecciona una palabra y
triple clic todo. El texto se recorre por grafemas: un emoji compuesto o una letra con tilde
combinada se borran de una vez. Tab sale del campo; las teclas pasan antes por los `on_key`.

### `textarea(value, *, placeholder="", rows=3, on_change=None, on_submit=None, key=None, **estilo)`

Como `text_input`, pero multilínea: Enter inserta un salto de línea y **Ctrl+Enter** (Cmd+Enter en
macOS) llama a `on_submit`. Las líneas largas se parten solas, y el campo **crece con el contenido**
a partir de un mínimo de `rows` líneas. Las flechas ↑ ↓ cambian de línea e Inicio/Fin van al
principio y al final de la línea. Para limitar su altura, ponlo dentro de un
`scroll(max_height=...)`: el cursor siempre se mantiene a la vista.

## Animaciones

Las animaciones se **declaran** en el elemento y las interpola el núcleo en cada frame, sin volver a
llamar a Python ni competir por el GIL. Cinco propiedades de estilo las activan:

```python
from aurora import animate

row(
    key=f"tarea-{t.id}",  # identidad estable: imprescindible para animar
    bg="$surface_pressed" if t.done else "$surface",
    transition=animate.spring(),  # funde bg, border_color, color, opacity y radius
    animate_layout=True,  # se desliza cuando el layout lo mueve
    enter=animate.slide(y=12),  # aparece subiendo y haciéndose visible
    exit=animate.zoom(0.95),  # se va encogiendo y desvaneciéndose
)
box(pulse=animate.pulse())  # late sin parar (indicadores de carga)
```

| Propiedad | Valores | Descripción |
|---|---|---|
| `transition` | `animate.spring(...)`, `animate.tween(...)` | Al reconstruir la vista, los cambios de `bg`, `border_color`, `color` (el del texto del propio nodo), `opacity` y `radius` se animan desde lo que se ve hacia el valor nuevo. Un color que aparece o desaparece se funde desde/hacia transparente. Es también la curva por defecto de las otras tres. El color heredado de un contenedor no se anima a través de los hijos: para eso, pon `transition` en el propio texto. |
| `animate_layout` | `True` o una curva | Cuando un layout cambia la caja del elemento (otro elemento aparece, se va, cambia de tamaño o se reordena), se desliza desde la caja que mostraba; su fondo, borde y sombra cambian de tamaño con ella y sus hijos se desplazan con él. Con `True` usa la curva de `transition` (o un muelle). Al redimensionar la ventana el layout salta, sin animarse. |
| `enter` | efecto | Valores desde los que **aparece** cuando entra en la vista. No se reproduce en el primer frame de la app (ni en `render_png`). |
| `exit` | efecto | Valores hacia los que **se va** cuando sale de la vista. Mientras dura se pinta una instantánea del elemento tal como estaba, encima de su capa: ya no ocupa sitio en el layout (los demás pueden deslizarse a su hueco con `animate_layout`) ni recibe eventos. Si vuelve a la vista antes de terminar, entra desde donde estaba. |
| `pulse` | `animate.pulse(...)` | Vaivén perpetuo de la opacidad (1 → `floor` → 1), para indicadores de carga. Nunca termina: mientras está visible, la app sigue pintando frames. |

Todo se anima **por `key`**: un elemento sin `key` explícita toma la identidad de su posición, así
que en listas que cambian dale siempre una. Mientras una animación de layout o un efecto
transforma un elemento, los clics usan su caja final (la de `pilot.rect`).

### Movimiento por defecto en los componentes

No hace falta declarar nada para que los componentes se sientan vivos: `switch`, `checkbox`,
`tabs`, `select`, `radio`, `segmented` y `slider` ya traen sus animaciones con una **escala común**
de duraciones cortas (el knob de un switch se desliza, la marca de una casilla entra encogiéndose,
el subrayado de las pestañas funde, el menú de un `select` aparece deslizándose, el pulgar de un
`segmented` se desliza hasta la opción activa y las barras de `progress` crecen hasta su valor).

`spinner` y `skeleton`, en cambio, laten con un **vaivén perpetuo** (`pulse`): mientras están
visibles la app sigue pintando frames y `pilot.settle()` agota sus frames sin llegar al reposo.

Si prefieres que nada se mueva —tests de snapshot, equipos que lo piden—, apágalo entero:

```python
App(view, motion=False)  # o AURORA_MOTION=0 en el entorno
```

Los efectos de entrada no se reproducen en el primer frame ni en `render_png` (y el vaivén nace a
opacidad plena): las capturas y la documentación siguen siendo deterministas.

### Curvas de tiempo

| Función | Descripción |
|---|---|
| `animate.spring(*, stiffness=380, damping=30, mass=1, delay=0)` | Muelle físico (por defecto): más `stiffness`, más rápido; menos `damping`, más rebote. Su duración sale de la física (~0,3 s con los valores por defecto) y, si el destino cambia a medias, sigue desde donde está. |
| `animate.tween(duration=0.25, *, easing="ease_out", delay=0)` | Duración fija en segundos con una curva de CSS: `"linear"`, `"ease"`, `"ease_in"`, `"ease_out"`, `"ease_in_out"`. |

`delay` (segundos) retrasa el comienzo; con él se escalonan las entradas de una lista
(`enter=animate.slide(y=8, transition=animate.spring(delay=i * 0.03))`).

### Vaivén perpetuo

`animate.pulse(duration=1.0, *, delay=0, floor=0.35)` baja la opacidad de 1 a `floor` y la sube
otra vez, sin terminar nunca. Se pasa en la propiedad **`pulse`** de un elemento (no en
`transition`) y es para indicadores de carga: `delay` escalona varios elementos y `floor` marca la
opacidad mínima.

```python
box(width=8, height=8, radius="$full", bg="$primary", pulse=animate.pulse(delay=0.15))
```

### Efectos de entrada y salida

Un efecto son cuatro valores relativos al elemento: opacidad, desplazamiento `x`/`y` en píxeles y
escala alrededor de su centro. Cada uno acepta `transition=` para usar otra curva que la del
elemento.

| Función | Efecto |
|---|---|
| `animate.fade(opacity=0.0)` | Solo opacidad. |
| `animate.slide(x=0, y=0, *, fade=True)` | Desplazamiento, por defecto desvaneciéndose. |
| `animate.zoom(scale=0.9, *, fade=True)` | Escala, por defecto desvaneciéndose. |
| `animate.effect(*, opacity=1, x=0, y=0, scale=1)` | Cualquier combinación. |

Los valores inválidos (rigidez no positiva, duración o retardo negativos, easing desconocido,
escala negativa) lanzan `ValueError` al crearlos.

### Tipos de `animate`

Las funciones de arriba devuelven valores inmutables (dataclasses congeladas) que se pueden
guardar, comparar y reutilizar entre elementos; sus campos son los argumentos de la función:

| Tipo | Lo crea | Campos |
|---|---|---|
| `animate.Spring` | `spring()` | `stiffness`, `damping`, `mass`, `delay` |
| `animate.Tween` | `tween()` | `duration`, `easing`, `delay` |
| `animate.Pulse` | `pulse()` | `duration`, `delay`, `floor` |
| `animate.Effect` | `fade()`, `slide()`, `zoom()`, `effect()` | `opacity`, `x`, `y`, `scale`, `transition` |

Y dos alias para anotar código propio: **`animate.Transition`** (`Spring | Tween`: lo que acepta
`transition=` o `animate_layout=`) y **`animate.Easing`** (el `Literal` de los nombres de curva de
`tween`).

```python
from aurora import animate

SUAVE: animate.Transition = animate.tween(0.4, easing="ease_in_out")


def entrada(i: int) -> animate.Effect:
    return animate.slide(y=8, transition=animate.spring(delay=i * 0.03))
```

En los tests, `pilot.frame(dt)` avanza las animaciones `dt` segundos y devuelve `True` mientras
alguna sigue en curso; `pilot.settle()` espera a que terminen todas (salidas incluidas).

## Propiedades de estilo

Las longitudes están en **píxeles lógicos**. Las propiedades marcadas con *H* se **heredan** de los
contenedores (como en CSS).

### Layout

| Propiedad | Valores | Por defecto | Descripción |
|---|---|---|---|
| `direction` | `"row"`, `"column"` | `"column"` | Eje principal. |
| `gap` | número | `0` | Espacio entre hijos. |
| `padding` | número · `(v, h)` · `(t, r, b, l)` | `0` | Relleno interior. |
| `align` | `"start"`, `"center"`, `"end"`, `"baseline"`, `"stretch"` | `"stretch"` | Alineación en el eje cruzado. `"baseline"` alinea textos de distinto tamaño por su línea base. En una columna que no estira, cada hijo mide lo que ocupa su contenido sin pasar del ancho de la columna (como `fit-content` en CSS): un texto largo, una fila o un `markdown` se parten en líneas en vez de salirse. |
| `justify` | `"start"`, `"center"`, `"end"`, `"between"`, `"around"`, `"evenly"` | `"start"` | Distribución en el eje principal. |
| `width`, `height` | número · `"50%"` | automático | Tamaño fijo o relativo al contenedor. |
| `min_width`, `max_width` | número | — | Límites de ancho. |
| `min_height`, `max_height` | número | — | Límites de alto. `max_height` en un `scroll` limita cuánto crece antes de desplazarse. |
| `grow` | número | `0` | Cuánto crece para ocupar espacio libre. |
| `shrink` | número | `1` | Cuánto se encoge si falta espacio. |
| `wrap` | `bool` | `False` | Permite saltar de línea a los hijos (rejillas de tarjetas). |
| `position` | `"absolute"` | relativo | Saca al elemento del flujo; se coloca con `top/right/bottom/left` respecto a su padre. Útil para modales, toasts y superposiciones. |
| `top`, `right`, `bottom`, `left` | número · `"50%"` | — | Desplazamientos para `position="absolute"`. Los porcentajes se resuelven contra la caja de relleno del padre (como la posición absoluta de CSS). |
| `overflow` | `"visible"`, `"hidden"` | `"visible"` | Con `"hidden"` el contenido que se sale de la caja se recorta (pintado **y** clics) sin tocar el layout. Los hijos se encogen para caber salvo que les des `shrink=0`: con él desbordan y es el recorte quien los oculta (así despliega el `accordion`). |
| `src` | ruta o `bytes` | — | Origen de una imagen. Usa la primitiva `image()`. |
| `fit` | `"contain"`, `"cover"`, `"fill"`, `"none"` | `"contain"` | Encaje de una imagen en su caja. |
| `scroll` | `"x"`, `"y"`, `"both"` | — | Convierte la caja en contenedor desplazable. Usa la primitiva `scroll()`, que añade buenos valores por defecto. |
| `scroll_anchor` | `bool` | `False` | En un `scroll`: cuando cambia el contenido (algo crece, aparece o se carga por encima de lo visible), corrige el desplazamiento para que el primer nodo que se veía arriba siga en su sitio; si estaba al final, el último que se veía abajo. Como `overflow-anchor` de CSS. `virtual_list` lo activa sin `item_height`. |
| `stick_to_end` | `bool` | `False` | En un `scroll`: empieza al final y, si está al final cuando el contenido crece, sigue al final. Para chats y registros. |
| `reveal` | `(top, bottom)` | — | En un `scroll`: franja de su contenido (en píxeles desde su inicio) que debe verse. Cuando cambia, el contenedor se desplaza lo justo para mostrarla; si no cambia, no interfiere con la rueda. Así sigue `tree` a la fila elegida. |

> **Truco: columnas de igual ancho.** `grow=1, width=0` en cada hijo de una `row` reparte el
> espacio a partes iguales, sin importar su contenido.

### Apariencia

| Propiedad | Valores | Descripción |
|---|---|---|
| `bg` | color | Color de fondo. |
| `bg_hover` | color | Fondo con el cursor encima (requiere `on_click` u `on_drag`). Transición animada. |
| `bg_pressed` | color | Fondo mientras se mantiene pulsado. Transición animada. |
| `gradient` | `(desde, hasta, ángulo)` | Gradiente lineal. Ángulo en grados: `0` = izquierda→derecha, `90` = arriba→abajo. Reemplaza a `bg`. |
| `radius` | número | Radio de las esquinas. Usa `999` (o `"$full"`) para píldoras y círculos. |
| `border_width` | número | Grosor del borde (también reserva espacio en el layout). |
| `border_color` | color | Color del borde. |
| `shadow` | `(dx, dy, blur, color)` | Sombra difuminada desplazada. |
| `opacity` | `0.0` – `1.0` | Opacidad del elemento y todos sus hijos. |
| `press_scale` | número | Escala al pulsar (p. ej. `0.96`). Animada. |
| `transition`, `animate_layout`, `enter`, `exit`, `pulse` | curvas y efectos de `animate` | Animaciones declarativas: `transition` funde los cambios de `bg`, `border_color`, `color`, `opacity` y `radius`; `pulse` (un `animate.pulse()`) hace latir la opacidad sin parar. Ver [Animaciones](#animaciones). |
| `scrollbar_color` | color | Color del pulgar de la barra de un `scroll` (se pinta translúcido). `scroll()` usa `$muted`. |
| `placeholder_color` | color | Color del placeholder de un campo de texto. Por defecto, el color del texto al 45 %. |
| `selection_color` | color | Fondo del texto seleccionado. Por defecto, `focus_color` translúcido. |
| `tooltip` | texto | Texto de ayuda que aparece al dejar el puntero encima. Ver [`tooltip`](#tooltipchild-tip). |
| `cursor` | `"default"`, `"pointer"`, `"text"`, `"grab"`, `"grabbing"`, `"col-resize"`, `"row-resize"`, `"ns-resize"`, `"ew-resize"`, `"nesw-resize"`, `"nwse-resize"`, `"crosshair"` | Cursor del ratón sobre el elemento y sus hijos (salvo que un hijo fije otro). Durante un `on_drag` se mantiene el del elemento arrastrado. |
| `drop_target` | `bool` | Zona de soltar: mientras se arrastra un elemento con `on_drag`, su [`DragEvent`](#dragevent) dice si el puntero está sobre ella (`target`) y en qué posición caería entre sus hijos arrastrables (`index`). |
| `window_drag` | `"move"` · `"n"`, `"s"`, `"e"`, `"w"`, `"ne"`, `"nw"`, `"se"`, `"sw"` | Pulsar en el elemento (fuera de sus controles) mueve la ventana —doble clic: maximizar o restaurar— o la redimensiona desde ese borde. Para barras de título propias: ver [Ventanas sin marco](#ventanas-sin-marco). |
| `capture` | `bool` | Barrera de eventos: los clics dentro no llegan a los ancestros. Úsalo en el contenido de un modal. |
| `placement`, `offset` | `"bottom"`, `"top-start"`, `"right-end"`… · número | Solo con `layer="overlay"`: coloca el elemento junto a su ancla —el hermano anterior que ocupa sitio en el flujo o, si no lo hay, el contenedor—, en ese lado y con esa alineación (`start`, `center` —la de por defecto— o `end`), a `offset` píxeles. Si no cabe se vuelca al lado opuesto, y nunca se sale de la ventana. Ver [`popover`](#popover). |
| `layer` | `"base"`, `"overlay"` | Con `"overlay"`, el elemento se maqueta en su sitio pero se pinta y recibe eventos **por encima de todo el árbol**, aunque se declare antes que otros. Ideal para desplegables, tooltips y modales. Se pinta en coordenadas absolutas: no hereda la `opacity` ni el `press_scale` de sus ancestros. Los clics siguen burbujeando por sus ancestros del árbol. |

### Texto

| Propiedad | Alias | Valores | Por defecto | |
|---|---|---|---|---|
| `font_size` | `size` | número | `14` | *H* |
| `font_weight` | `weight` | `100`–`900` | `400` | *H* |
| `color` | — | color | `$text` | *H* |
| `font_family` | `family` | nombre de fuente | fuente del tema (`Inter`) | *H* |
| `line_height` | — | múltiplo del tamaño (`1.4`) | el de la fuente | *H* |
| `letter_spacing` | — | número (px, admite negativos) | `0` | *H* |
| `focus_color` | — | color del anillo de foco | `$primary` | *H* |
| `tooltip_bg`, `tooltip_color` | — | colores de la burbuja de los tooltips | `$text`, `$background` | *H* |
| `max_lines` | — | entero | sin límite | Corta con `…` al superar ese número de líneas. |
| `text_align` | — | `"left"`, `"center"`, `"right"` | `"left"` | Alineación dentro del ancho del texto. |

Si la fuente pedida no está instalada, se usa la de reserva del sistema, y los glifos que falten
(emoji, símbolos) se buscan automáticamente en otras fuentes.

## Temas y tokens

En cualquier propiedad que acepte color o radio puedes usar un **token**: un string que empieza
por `$` y se resuelve con el tema activo.

```python
box(bg="$surface", radius="$lg", shadow=(0, 8, 24, "$shadow"))
```

### Tokens incluidos

| Colores | Uso |
|---|---|
| `$background` | Fondo de la ventana |
| `$surface`, `$surface_hover`, `$surface_pressed` | Tarjetas, paneles y sus estados |
| `$border` | Bordes sutiles |
| `$text`, `$muted` | Texto principal y secundario |
| `$primary`, `$primary_hover`, `$primary_pressed` | Color de marca y sus estados |
| `$accent`, `$success`, `$danger` | Acentos y semántica |
| `$shadow`, `$glow` | Sombras neutras y brillo de marca |

| Radios | |
|---|---|
| `$sm` `8` · `$md` `12` · `$lg` `18` · `$full` `999` | |

### Temas incluidos y temas propios

`MIDNIGHT` (oscuro, por defecto) y `DAYLIGHT` (claro) definen todos los tokens. Para crear el tuyo:

```python
from aurora import MIDNIGHT, Theme

OCEAN = Theme(
    colors={
        **MIDNIGHT.colors,
        "primary": "#0EA5E9",
        "primary_hover": "#38BDF8",
        "primary_pressed": "#0284C7",
        "glow": "#0EA5E940",
    },
    radius=MIDNIGHT.radius,
    font_family="Inter",
)
```

Un token que no existe en el tema lanza `KeyError` al construir la vista, para que los errores
de escritura se detecten enseguida.

`Theme.resolve(value)` hace esa traducción a mano: devuelve el color o el radio de un `"$token"`,
resuelve cada elemento de una tupla (`(0, 8, 24, "$shadow")`) y deja igual cualquier otro valor.
Sirve para usar los colores del tema fuera de las propiedades de estilo (al dibujar en un `canvas`,
por ejemplo):

```python
MIDNIGHT.resolve("$primary")  # "#7C5CFF"
MIDNIGHT.resolve((0, 8, 24, "$shadow"))  # (0, 8, 24, "#00000066")
```

## Formatos de valores

| Tipo | Formato |
|---|---|
| Color | `"#rgb"`, `"#rrggbb"` o `"#rrggbbaa"` (el último par es la opacidad: `"#00000080"` = negro al 50 %). También tokens `"$nombre"`. |
| Longitud | Número en píxeles lógicos, o `"NN%"` en `width`/`height`. |
| Ángulo | Grados (`float`). |

Un color mal escrito lanza `ValueError` con el valor problemático en el mensaje.

## Empaquetado: `aurora build`

```bash
aurora build                 # empaqueta main.py (o app.py) en dist/
aurora build app.py --name "Mi App" --icon assets/icon.ico --include assets
```

Convierte la app en un **ejecutable distribuible** que no necesita Python instalado: un solo
archivo (`dist/main.exe` en Windows, `dist/main` en Linux) o, en macOS, una `dist/main.app`.
Por debajo usa [PyInstaller](https://pyinstaller.org), que es una dependencia opcional:

```bash
uv add --dev "aurora-ui[build]"    # o: pip install "aurora-ui[build]"
```

Se empaqueta para el sistema en el que se ejecuta (para Windows, macOS y Linux hay que construir
en cada uno; en CI, una matriz). También funciona como `python -m aurora build`.

### Opciones

Todas tienen su equivalente en `[tool.aurora.build]` de `pyproject.toml`; las de la línea de
comandos tienen prioridad, salvo `--include`, que se suma a `include`.

| Opción | `pyproject.toml` | Por defecto | Descripción |
|---|---|---|---|
| `script` | `script` | `main.py` o `app.py` | Script de la app. |
| `--name` | `name` | nombre del script | Nombre del ejecutable. |
| `--icon` | `icon` | — | Icono: `.ico` en Windows, `.icns` en macOS. Otros formatos (PNG) se convierten si está instalado Pillow. Linux no incrusta iconos en el ejecutable. |
| `--include RUTA` | `include` (lista) | — | Archivo o carpeta que se copia con la app, con la misma ruta relativa al script (`assets/logo.png` sigue siendo `assets/logo.png`). Lo que está fuera de la carpeta del script va a la raíz. Repetible. |
| `--onefile` / `--onedir` | `onefile` | `true` | Un solo archivo, o una carpeta con el ejecutable y sus bibliotecas, que arranca antes (no se descomprime en cada inicio). En macOS sin consola siempre se genera una `.app`. |
| `--console` / `--windowed` | `console` | `false` | Mantener la ventana de consola (útil para ver `print` y errores mientras pruebas). |
| `--upx` / `--no-upx` | `upx` | `false` | Comprime los binarios con UPX (que debe estar instalado): el ejecutable pesa menos, a costa de falsos positivos de antivirus y un arranque algo más lento. |
| `--dist` | `dist` | `dist` | Carpeta de salida. Los archivos intermedios van a `build/`. |
| `--clean` | — | — | Borra la caché de PyInstaller antes de empaquetar. |

UPX viene desactivado a propósito: además de lo anterior, el resultado del build no debe depender
de si la máquina tiene UPX instalado. Si lo activas y PyInstaller avisa de que algún binario no es
comprimible (`python3.dll` y similares), es normal: lo deja sin comprimir y el build termina igual.

```toml
[tool.aurora.build]
script = "app.py"
name = "Monitor"
icon = "assets/icon.ico"
include = ["assets"]
```

Las rutas de `pyproject.toml` son relativas a ese archivo (que se busca desde el directorio
actual hacia arriba); las de la línea de comandos, al directorio actual. Una clave desconocida,
un tipo incorrecto o una ruta que no existe se informan antes de empaquetar.

### `resource(path)`

```python
from aurora import image, resource

image(resource("assets/logo.svg"), width=32)
```

Devuelve la ruta absoluta de un recurso de la app. Una ruta relativa se resuelve desde la
**carpeta del script principal**, no desde el directorio de trabajo; dentro del ejecutable, desde
donde quedan los archivos de `include`, que conservan su estructura. Así funciona igual con
`python app.py`, con doble clic en el ejecutable o lanzándolo desde otra carpeta. Una ruta
absoluta se devuelve tal cual.

## Avisos de obsolescencia

`aurora.AuroraDeprecationWarning` (subclase de `FutureWarning`) es el aviso que emite cualquier parte
de la API marcada como obsoleta: dice desde qué versión lo está, en cuál se eliminará y qué usar
en su lugar. Se ve por defecto en la consola; para que los tests de tu app fallen al usar algo
obsoleto:

```toml
[tool.pytest.ini_options]
filterwarnings = ["error::aurora.AuroraDeprecationWarning"]
```

Los plazos y qué cuenta como API pública están en la [política de estabilidad](stability.md).
