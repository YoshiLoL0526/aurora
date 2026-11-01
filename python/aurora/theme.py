"""Design tokens. En los estilos se referencian como "$nombre" (p. ej. bg="$surface")."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ThemeTokenError(KeyError):
    """Un `"$token"` que no está en el tema. Hereda de `KeyError` (lo que se
    lanzaba antes) y sugiere el token más parecido."""

    def __init__(self, token: str, known: list[str], prop: str | None = None) -> None:
        import difflib  # solo al fallar: no cuesta en el arranque

        self.token = token
        self.prop = prop
        where = f" en {prop!r}" if prop else ""
        message = f"token de tema desconocido{where}: {token!r}."
        close = difflib.get_close_matches(token, [f"${name}" for name in known], n=1)
        if close:
            message += f" ¿Quisiste decir {close[0]!r}?"
        super().__init__(message)

    def __str__(self) -> str:
        # `KeyError` muestra su argumento entre comillas: el mensaje se lee mejor sin ellas.
        return str(self.args[0])


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
            raise ThemeTokenError(value, [*self.colors, *self.radius])
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


DAYLIGHT = Theme(
    colors={
        "background": "#F4F5F9",
        "surface": "#FFFFFF",
        "surface_hover": "#F0F1F6",
        "surface_pressed": "#E6E8F0",
        "border": "#E3E5EE",
        "text": "#141826",
        "muted": "#6B7189",
        "primary": "#6847F5",
        "primary_hover": "#7A5CFF",
        "primary_pressed": "#5636E0",
        "accent": "#0FB89C",
        "success": "#12A26B",
        "danger": "#E04848",
        "shadow": "#1A1F3A14",
        "glow": "#6847F533",
    },
    radius=MIDNIGHT.radius,
)
