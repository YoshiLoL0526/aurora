# Galería

Los ejemplos de la carpeta [`examples/`](../examples/README.md) del repositorio, ejecutados al
construir esta página. Para abrirlos en una ventana:

```bash
uv run examples/studio.py
```

## Aurora Studio

Una app completa: navegación entre vistas con transición, kanban con búsqueda y menús de acción,
gráfico interactivo, formulario de nueva tarea (Ctrl+N), ajustes con `tabs`/`switch`/`select`/
`textarea` animados por defecto y una zona de peligro en acordeón, modal con confirmación, toasts,
tooltips y tema claro/oscuro. Código: [`examples/studio.py`](../examples/studio.py).

```python live file=examples/studio.py alt="Aurora Studio, vista de resumen"
```

```python live file=examples/studio.py alt="Aurora Studio, tablero kanban filtrado"
page.set("tablero")
toggle_tag("backend")
```

## Hola mundo

Lo esencial: layout, tarjetas de métricas, botones y un contador reactivo.
Código: [`examples/hello.py`](../examples/hello.py).

```python live file=examples/hello.py theme=dark alt="Panel de control con métricas y un contador"
clicks.set(1280)
```

## Gráficos

Línea de dos series (polars), área, barras por categoría, dispersión y una señal de un millón de
puntos con zoom y pan. Código: [`examples/charts.py`](../examples/charts.py).

```python live file=examples/charts.py alt="Panel con gráficos de línea, área, barras y dispersión"
```

## Tabla

100 000 clientes con ordenación por columna, columnas redimensionables y filas virtualizadas.
Código: [`examples/table.py`](../examples/table.py).

```python live file=examples/table.py alt="Tabla de clientes con búsqueda y badges de estado"
```

## Canvas

Dibujo inmediato: un gráfico de líneas con rejilla y un indicador circular.
Código: [`examples/canvas.py`](../examples/canvas.py).

```python live file=examples/canvas.py alt="Gráfico de líneas y un indicador circular dibujados con canvas"
```

## Animaciones

Lista de tareas que se reordena con animaciones de layout, de entrada y de salida.
Código: [`examples/animate.py`](../examples/animate.py).

```python live file=examples/animate.py alt="Lista de tareas animada"
```
