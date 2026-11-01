# Lista de tareas con filtros

Escribe en `app.py` una app de Aurora con una lista de tareas.

- Un campo con `key="new"` para escribir una tarea y un botón «Añadir» con `key="add"`; pulsar
  Enter en el campo también la añade. Tras añadir, el campo se vacía. Una tarea vacía no se añade.
- Cada tarea se numera en orden de creación empezando por 1. Su fila tiene `key="task-<n>"` y una
  casilla para marcarla como hecha con `key="toggle-<n>"` (por ejemplo `task-1` y `toggle-1`).
- Tres filtros con `key="filter-all"`, `key="filter-pending"` y `key="filter-done"`: todas, solo
  pendientes y solo hechas. Las filas que el filtro oculta no se pintan.
- Un contador con `key="remaining"` que muestra `N pendientes` (por ejemplo `2 pendientes`).
- Tiene que verse bien en una ventana de 520×600.
