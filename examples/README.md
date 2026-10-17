# Ejemplos

Todos se ejecutan desde la raíz del repositorio con `uv run`. Los que aceptan `--png` renderizan
sin abrir ventana, útil para ver el resultado en un servidor o en CI.

| Ejemplo | Qué muestra | Comando |
|---|---|---|
| [`hello.py`](hello.py) | Lo esencial: layout, tarjetas de métricas, botones y un contador reactivo con deslizador de paso. | `uv run examples/hello.py` |
| [`studio.py`](studio.py) | Una app completa: navegación entre vistas con transición, kanban con búsqueda, menús de acciones y densidad ajustable, gráfico interactivo, formulario de nueva tarea (Ctrl+N), ajustes con `tabs`/`switch`/`checkbox`/`radio`/`select`/`textarea`, un deslizador y zona de peligro en acordeón, diálogo con confirmación, toasts, tooltips y tema claro/oscuro. | `uv run examples/studio.py` |
| [`canvas.py`](canvas.py) | Dibujo inmediato con `canvas`: gráfico de líneas con rejilla y un indicador circular que se redibujan al cambiar los datos; el deslizador mueve la carga. | `uv run examples/canvas.py` |
| [`charts.py`](charts.py) | Gráficos nativos con `chart`: línea de dos series (polars), área que se actualiza con datos mutados en sitio, barras por categoría con la forma elegible en un `segmented`, dispersión y una señal de un millón de puntos con zoom y pan. | `uv run examples/charts.py` |
| [`table.py`](table.py) | Tabla de 100 000 clientes con `table`: ordenación por columna, columnas redimensionables arrastrando el borde de la cabecera, filas virtualizadas, celdas con `avatar` y `badge`, búsqueda y selección de fila. | `uv run examples/table.py` |
| [`animate.py`](animate.py) | Animaciones declarativas: lista de tareas que se reordena, filas que entran, salen y funden su color con suavidad, barra de progreso que crece y un `dialog` con su animación integrada. | `uv run examples/animate.py` |
| [`windows.py`](windows.py) | Escritorio de verdad: la lista de notas en una ventana y el detalle en otra, con los `Signal` compartidos, el diálogo nativo de abrir archivo, menús contextuales en las tarjetas y barra de menús con atajos. | `uv run examples/windows.py` |
| [`notepad.py`](notepad.py) | Bloc de notas: barra de menús con atajos (`mod+o`/`mod+s`/`mod+n`), diálogos nativos de abrir y guardar, título que refleja el archivo y los cambios sin guardar, y confirmación al salir (menú y X de la ventana). | `uv run examples/notepad.py` |
| [`tray.py`](tray.py) | Vive en la bandeja: cerrar la ventana no termina la app (se reabre desde el icono o el menú), menú de bandeja con submenú y «Salir», notificación del sistema al añadir un recordatorio, y `app.main` para mostrar/ocultar la principal. | `uv run examples/tray.py` |
| [`brand.py`](brand.py) | Genera el banner y el logo del README con la propia librería. | `uv run examples/brand.py` |

```bash
uv run examples/hello.py --png hola.png
uv run examples/studio.py --png capturas/
```

<p align="center">
  <img src="../docs/studio/2-tablero.png" width="49%"> <img src="../docs/studio/4-equipo-claro.png" width="49%">
</p>
