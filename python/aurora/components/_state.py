"""Estado por `key` que los componentes conservan entre reconstrucciones.

La vista se reconstruye entera tras cada cambio, así que lo que debe sobrevivir
(un menú abierto, un arrastre a medias, la zona visible de una lista) vive aquí,
indexado por la `key` del componente, no en el árbol de elementos.
"""

from __future__ import annotations

from ..signal import Signal

# Abierto/cerrado de cada `menu` y `select`.
_OPEN: dict[str, Signal[bool]] = {}
# Valor con el que empezó el arrastre de cada `slider`.
_DRAG_START: dict[str, float] = {}
# Zona visible de cada `virtual_list` (desplazamiento y alto), o `None` sin medir.
_VIEWPORTS: dict[str, Signal[tuple[float, float] | None]] = {}
