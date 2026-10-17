# Galería

Los ejemplos de la carpeta [`examples/`](../examples/README.md) del repositorio, ejecutados al
construir esta página. Para abrirlos en una ventana:

```bash
uv run examples/studio.py
```

## Aurora Studio

Una app completa: navegación entre vistas con transición, kanban con búsqueda y menús de acción,
gráfico interactivo, formulario de nueva tarea (Ctrl+N), ajustes con `tabs`/`switch`/`checkbox`/
`radio`/`select`/`textarea`, un deslizador y una zona de peligro en acordeón —todo con el
movimiento por defecto de los componentes—, diálogo con confirmación, toasts, tooltips y tema
claro/oscuro. Código: [`examples/studio.py`](../examples/studio.py).

```python live file=examples/studio.py alt="Aurora Studio, vista de resumen"
```

```python live file=examples/studio.py alt="Aurora Studio, tablero kanban filtrado"
page.set("tablero")
toggle_tag("backend")
```

```python live file=examples/studio.py alt="Aurora Studio, ajustes con radio y deslizador"
page.set("ajustes")
```

## Hola mundo

Lo esencial: layout, tarjetas de métricas, botones y un contador reactivo cuyo paso se ajusta con
un deslizador. Código: [`examples/hello.py`](../examples/hello.py).

```python live file=examples/hello.py theme=dark alt="Panel de control con métricas y un contador"
clicks.set(1280)
step.set(10.0)
```

## Gráficos

Línea de dos series (polars), área, barras por categoría —con un `segmented` que cambia su
forma—, dispersión y una señal de un millón de puntos con zoom y pan.
Código: [`examples/charts.py`](../examples/charts.py).

```python live file=examples/charts.py alt="Panel con gráficos de línea, área, barras y dispersión"
```

```python live file=examples/charts.py alt="La tarjeta de cierres vista como área"
forma.set("area")
```

## Varias ventanas

Lista de notas en la principal y detalle en una segunda ventana, compartiendo los `Signal`, con el
diálogo nativo de abrir archivo, menús contextuales en las tarjetas y barra de menús con atajos.
(En la captura headless solo se ve la principal.) Código:
[`examples/windows.py`](../examples/windows.py).

```python live file=examples/windows.py alt="Lista de notas en la ventana principal"
```

```python live file=examples/windows.py theme=dark alt="La misma lista con otra nota seleccionada"
seleccion.set(2)
```

## Bloc de notas

Barra de menús con atajos del sistema (`mod+o`, `mod+s`, `mod+n`), diálogos nativos de abrir y
guardar, y confirmación al salir si hay cambios sin guardar —tanto desde el menú como desde la X.
Código: [`examples/notepad.py`](../examples/notepad.py).

```python live file=examples/notepad.py alt="Bloc de notas vacío"
```

```python live file=examples/notepad.py theme=dark alt="Bloc de notas con un documento sin guardar"
contenido.set("Notas de la reunión\n\n- Roadmap hacia la 1.0\n- Ejemplos nuevos")
```

## Bandeja del sistema

Cerrar la ventana no termina la app: sigue en la bandeja (se reabre con `app.main.open()` desde el
menú del icono) y solo «Salir» la termina. Al añadir un recordatorio, `app.notify` muestra una
**notificación del sistema** aunque la ventana esté cerrada. Código:
[`examples/tray.py`](../examples/tray.py).

```python live file=examples/tray.py alt="Recordatorios con la app viviendo en la bandeja"
```

## Tabla

100 000 clientes con ordenación por columna, columnas redimensionables, filas virtualizadas y
celdas con avatar. Código: [`examples/table.py`](../examples/table.py).

```python live file=examples/table.py alt="Tabla de clientes con avatares y badges de estado"
```

```python live file=examples/table.py alt="Tabla filtrada por «ana»"
busqueda.set("ana")
```

## Canvas

Dibujo inmediato: un gráfico de líneas con rejilla y un indicador circular que sigue al
deslizador. Código: [`examples/canvas.py`](../examples/canvas.py).

```python live file=examples/canvas.py alt="Gráfico de líneas y un indicador circular dibujados con canvas"
```

```python live file=examples/canvas.py alt="Indicador circular al 88 %, en rojo"
load.set(0.88)
```

## Animaciones

Lista de tareas que se reordena con animaciones de layout, de entrada y de salida, una barra de
progreso que crece y un `dialog` con su animación integrada.
Código: [`examples/animate.py`](../examples/animate.py).

```python live file=examples/animate.py alt="Lista de tareas con una completada"
toggle(0)
```

```python live file=examples/animate.py alt="Diálogo modal con su entrada animada"
modal.set(True)
```
