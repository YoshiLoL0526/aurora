"""Design tokens. En los estilos se referencian como "$nombre" (p. ej. bg="$surface")."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Theme:
    colors: dict[str, str] = field(default_factory=dict)
    radius: dict[str, float] = field(default_factory=dict)
    font_family: str = "Inter"

    def resolve(self, value: Any) -> Any:
        if isinstance(value, str) and value.startswith("$"):
            name = value[1:]
            if name in self.colors:
                return self.colors[name]
            if name in self.radius:
                return self.radius[name]
            raise KeyError(f"token de tema desconocido: {value}")
        if isinstance(value, tuple):
            return tuple(self.resolve(v) for v in value)
        return value


MIDNIGHT = Theme(
    colors={
        "background": "#0B0D14",
        "surface": "#131722",
        "surface_hover": "#1A1F2E",
        "surface_pressed": "#20263A",
        "border": "#252B3B",
        "text": "#E6E8F0",
        "muted": "#8A91A8",
        "primary": "#7C5CFF",
        "primary_hover": "#8D72FF",
        "primary_pressed": "#6A48F5",
        "accent": "#22D3B6",
        "success": "#34D399",
        "danger": "#F87171",
        "shadow": "#00000066",
        "glow": "#7C5CFF40",
    },
    radius={"sm": 8.0, "md": 12.0, "lg": 18.0, "full": 999.0},
)
