"""Estado por `key` que los componentes conservan entre reconstrucciones.

La vista se reconstruye entera tras cada cambio, así que lo que debe sobrevivir
(un menú abierto, un arrastre a medias, la zona visible de una lista) vive aquí,
indexado por la `key` del componente, no en el árbol de elementos.
"""

from __future__ import annotations

from typing import Any

from ..signal import Signal

# Abierto/cerrado de cada `menu` y `select`.
_OPEN: dict[str, Signal[bool]] = {}
# Valor con el que empezó el arrastre de cada `slider`.
_DRAG_START: dict[str, float] = {}
# Zona visible de cada `virtual_list` (desplazamiento y alto), o `None` sin medir.
_VIEWPORTS: dict[str, Signal[tuple[float, float] | None]] = {}
# Texto a medio escribir de cada `number_input` (`None`: se muestra el valor).
_DRAFTS: dict[str, Signal[str | None]] = {}
# Lo que se escribe en cada `combobox` (`None`: se muestra la opción elegida) y
# la opción resaltada de su lista.
_QUERIES: dict[str, Signal[str | None]] = {}
_ACTIVE: dict[str, Signal[int]] = {}
# Mes que muestra el calendario de cada `date_picker`: `(año, mes)`.
_MONTHS: dict[str, Signal[tuple[int, int]]] = {}
# Tamaño del primer panel de cada `splitter` sin `Signal` propio, y lo que mide
# su contenedor en el eje del reparto (lo avisa `on_resize`).
_SPLITS: dict[str, Signal[float]] = {}
_EXTENTS: dict[str, Signal[float | None]] = {}
# Identidades desplegadas y nodo elegido de cada `tree` sin `Signal` propios.
_TREE_OPEN: dict[str, Signal[set[Any]]] = {}
_TREE_SELECTED: dict[str, Signal[Any]] = {}
# Tono, saturación y brillo de cada `color_picker` (el tono no sobrevive a un gris).
_HSV: dict[str, Signal[tuple[float, float, float]]] = {}
# Altos medidos de las filas de cada `virtual_list` de alto variable, y una
# versión que cambia cuando se corrige alguno (para reconstruir la vista).
_HEIGHTS: dict[str, Any] = {}
# Arrastre en curso de cada grupo de `sortable` (`None`: ninguno), sus listas
# construidas (por key) y el último anuncio para el lector de pantalla
# (`(lista donde se anuncia, texto)`).
_DRAGS: dict[str, Signal[Any]] = {}
_ZONES: dict[str, dict[str, Any]] = {}
_ANNOUNCE: dict[str, Signal[tuple[str, str]]] = {}
