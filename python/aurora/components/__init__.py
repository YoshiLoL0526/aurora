"""Componentes con estilo por defecto, construidos solo con primitivas.

Casi ningún componente necesita código nativo: el núcleo Rust sabe pintar
cajas, texto, sombras y gradientes, animar estados hover/pressed y editar texto
(el nodo `input`). Todo lo demás se compone aquí, en Python.

El paquete se organiza por familias (`basic`, `forms`, `navigation`, `overlays`,
`pickers`, `feedback`, `lists`) y este módulo reúne la API pública que expone `aurora`.
"""

from __future__ import annotations

from .basic import avatar, badge, button, card, divider, stat
from .feedback import progress, skeleton, spinner, toast
from .forms import checkbox, field, number_input, radio, slider, switch, text_input, textarea
from .lists import virtual_list
from .navigation import accordion, pages, segmented, tabs
from .overlays import dialog, menu, select, tooltip
from .pickers import combobox, date_picker

__all__ = [
    "accordion",
    "avatar",
    "badge",
    "button",
    "card",
    "checkbox",
    "combobox",
    "date_picker",
    "dialog",
    "divider",
    "field",
    "menu",
    "number_input",
    "pages",
    "progress",
    "radio",
    "segmented",
    "select",
    "skeleton",
    "slider",
    "spinner",
    "stat",
    "switch",
    "tabs",
    "text_input",
    "textarea",
    "toast",
    "tooltip",
    "virtual_list",
]
