"""Guiones de interacción para `aurora pilot`: una gramática mínima sobre `Pilot`.

Un guion es una lista de pasos separados por `;` o por saltos de línea; cada paso es un comando y
sus argumentos, separados por espacios y con comillas (como en la shell) si un argumento lleva
espacios o `;`; la barra invertida no escapa nada (las rutas de Windows se escriben tal cual).
Las líneas que empiezan por `#` son comentarios. La gramática completa está en `COMMANDS` y en
`docs/reference.md` (§ «Comprobar desde la terminal»).

El guion entero se valida antes de ejecutar nada (`parse`); `Runner.run` ejecuta los pasos en
orden y se para en el primero que falla.
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import _tree
from ._core import Pilot
from ._headless import ScriptError

FRAME = 1 / 60


class ScriptSyntaxError(Exception):
    """El guion está mal escrito (un comando desconocido, faltan argumentos…)."""


class StepError(Exception):
    """Un paso no se pudo hacer (una key que no está, una comprobación que no se cumple…)."""


@dataclass
class Step:
    """Un paso del guion: su número (desde 1), el comando y sus argumentos."""

    number: int
    name: str
    args: list[str]
    line: int  # línea del guion, desde 1

    @property
    def source(self) -> str:
        return shlex.join([self.name, *self.args])


@dataclass
class Result:
    """Lo que dio un paso: `output` es texto para mostrar (el árbol de `tree`, la ruta de `shot`)
    y `data`, lo mismo en datos (para `--json`)."""

    step: Step
    ok: bool = True
    output: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    script_error: ScriptError | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"step": self.step.number, "command": self.step.source, "ok": self.ok}
        d.update(self.data)
        if self.error is not None:
            d["error"] = self.error
        if self.script_error is not None:
            d["exception"] = self.script_error.to_dict()
        return d


@dataclass
class Command:
    usage: str
    help: str
    min_args: int
    max_args: int | None  # None: el resto de la línea


# La gramática: nombre → uso, ayuda y número de argumentos. Las keys son las del árbol
# (`aurora tree`); X, Y, DX, DY, W y H, píxeles lógicos.
COMMANDS: dict[str, Command] = {
    "click": Command("click KEY", "clic en el centro del nodo", 1, 1),
    "click_at": Command("click_at X Y", "clic en ese punto", 2, 2),
    "type": Command("type TEXTO", "escribe en el campo enfocado (`\\n` es Enter)", 1, None),
    "press": Command("press COMBO", "pulsa una tecla o combinación: enter, tab, shift+tab, ctrl+s", 1, 1),
    "focus": Command("focus KEY", "enfoca el nodo como con el teclado", 1, 1),
    "hover": Command("hover KEY", "pone el puntero sobre el centro del nodo", 1, 1),
    "move": Command("move X Y", "mueve el puntero a ese punto", 2, 2),
    "leave": Command("leave", "saca el puntero de la ventana", 0, 0),
    "scroll": Command("scroll KEY DY [DX]", "desplaza bajo el nodo (positivo: hacia el final)", 2, 3),
    "drag": Command("drag KEY DX DY", "arrastra desde el centro del nodo y suelta", 3, 3),
    "drag_to": Command("drag_to KEY DESTINO | drag_to KEY X Y", "arrastra hasta otro nodo o un punto", 2, 3),
    "a11y": Command("a11y KEY ACCIÓN [VALOR]", "acción de lector: click, focus, set_value…", 2, 3),
    "wait": Command("wait SEGUNDOS", "avanza el tiempo (tooltips, temporizadores)", 1, 1),
    "frame": Command("frame [N]", "avanza N frames (1 por defecto)", 0, 1),
    "settle": Command("settle", "avanza hasta que acaben las transiciones", 0, 0),
    "resize": Command("resize W H | resize WxH", "cambia el tamaño de la ventana", 1, 2),
    "shot": Command("shot RUTA [KEY]", "guarda el frame (o la caja de KEY) como PNG", 1, 2),
    "tree": Command("tree [KEY]", "imprime el árbol (o el subárbol de KEY)", 0, 1),
    "expect": Command(
        "expect exists|missing|focused|checked|unchecked KEY · expect text TEXTO [in KEY] · "
        "expect value KEY TEXTO · expect focused none",
        "comprueba el estado; si no se cumple, el paso falla",
        2,
        4,
    ),
}
# Pasos que no esperan a que acaben las transiciones: avanzan el tiempo a mano.
_MANUAL_TIME = {"wait", "frame", "settle"}
_EXPECT = {"exists", "missing", "focused", "checked", "unchecked", "text", "value"}


def usage() -> str:
    """La gramática en texto, un comando por línea."""
    width = max(len(c.usage) for c in COMMANDS.values() if c is not COMMANDS["expect"])
    lines = [f"  {c.usage:<{width}}  {c.help}" for n, c in COMMANDS.items() if n != "expect"]
    lines.append(f"  {COMMANDS['expect'].usage}")
    lines.append(f"  {'':<{width}}  {COMMANDS['expect'].help}")
    return "\n".join(lines)


def parse(text: str) -> list[Step]:
    """Los pasos del guion, ya validados. `ScriptSyntaxError` con la línea si alguno está mal."""
    steps: list[Step] = []
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lexer = shlex.shlex(raw, posix=True, punctuation_chars=";")
        lexer.whitespace_split = True
        lexer.commenters = ""
        lexer.escape = ""  # la barra invertida es literal: rutas de Windows y `\n` en `type`
        try:
            tokens = list(lexer)
        except ValueError as e:
            raise ScriptSyntaxError(f"línea {number}: {e} en {raw.strip()!r}") from e
        current: list[str] = []
        for token in [*tokens, ";"]:
            if token and set(token) == {";"}:
                if current:
                    steps.append(_step(len(steps) + 1, current, number))
                current = []
            else:
                current.append(token)
    if not steps:
        raise ScriptSyntaxError("el guion no tiene ningún paso")
    return steps


def _step(number: int, tokens: list[str], line: int) -> Step:
    name, args = tokens[0], tokens[1:]
    where = f"paso {number} ({shlex.join(tokens)!r})"
    command = COMMANDS.get(name)
    if command is None:
        import difflib

        close = difflib.get_close_matches(name, list(COMMANDS), n=1)
        hint = f" ¿Quisiste decir {close[0]!r}?" if close else ""
        raise ScriptSyntaxError(f"{where}: comando desconocido {name!r}.{hint} Comandos:\n{usage()}")
    if len(args) < command.min_args or (command.max_args is not None and len(args) > command.max_args):
        raise ScriptSyntaxError(f"{where}: uso: {command.usage}")
    step = Step(number, name, args, line)
    try:
        _validate(step)
    except ValueError as e:
        raise ScriptSyntaxError(f"{where}: {e} (uso: {command.usage})") from e
    return step


def _number(value: str, what: str) -> float:
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"{what} debe ser un número, no {value!r}") from None


def _validate(step: Step) -> None:
    """Comprueba los tipos de los argumentos (sin ejecutar nada)."""
    a = step.args
    match step.name:
        case "click_at" | "move":
            _number(a[0], "X"), _number(a[1], "Y")
        case "scroll" | "drag":
            for value in a[1:]:
                _number(value, "el desplazamiento")
        case "drag_to" if len(a) == 3:
            _number(a[1], "X"), _number(a[2], "Y")
        case "wait":
            if _number(a[0], "SEGUNDOS") < 0:
                raise ValueError("SEGUNDOS no puede ser negativo")
        case "frame" if a:
            if not a[0].isdigit():
                raise ValueError(f"N debe ser un entero positivo, no {a[0]!r}")
        case "resize":
            _size(a)
        case "expect":
            _expect_args(a)


def _size(args: list[str]) -> tuple[float, float]:
    parts = args[0].lower().split("x") if len(args) == 1 else args
    if len(parts) != 2:
        raise ValueError(f"tamaño {args[0]!r}: usa ANCHOxALTO (800x600) o ANCHO ALTO")
    w, h = _number(parts[0], "W"), _number(parts[1], "H")
    if w <= 0 or h <= 0:
        raise ValueError("el tamaño debe ser positivo")
    return w, h


def _expect_args(a: list[str]) -> None:
    what = a[0]
    if what not in _EXPECT:
        raise ValueError(f"no se puede comprobar {what!r} (sí: {', '.join(sorted(_EXPECT))})")
    if what == "text":
        if len(a) not in (2, 4) or (len(a) == 4 and a[2] != "in"):
            raise ValueError("uso: expect text TEXTO [in KEY]")
    elif what == "value":
        if len(a) != 3:
            raise ValueError("uso: expect value KEY TEXTO")
    elif len(a) != 2:
        raise ValueError(f"uso: expect {what} KEY")


# ---------------------------------------------------------------------------
# Ejecución


class Runner:
    """Ejecuta pasos sobre un `pilot` con una ventana de `size`. Las rutas relativas de `shot`
    se resuelven desde `cwd`."""

    def __init__(self, pilot: Pilot, size: tuple[float, float], *, cwd: Path | None = None) -> None:
        self.pilot = pilot
        self.size = size
        self.cwd = cwd or Path.cwd()

    def snapshot(self) -> _tree.Snapshot:
        return _tree.snapshot(self.pilot, self.size)

    def key(self, key: str) -> str:
        """`key` si está pintada; si no, `StepError` con keys parecidas."""
        snap = self.snapshot()
        if snap.find(key) is None:
            raise StepError(snap.missing(key))
        return key

    def run(self, steps: list[Step]) -> Iterator[Result]:
        """Ejecuta los pasos en orden; el último resultado es el del paso que falló, si alguno."""
        for step in steps:
            result = Result(step)
            try:
                self.do(step, result)
                if step.name not in _MANUAL_TIME:
                    self.pilot.settle()
            except StepError as e:
                result.ok, result.error = False, str(e)
            except ScriptError as e:
                result.ok, result.error, result.script_error = False, e.format(), e
            except Exception as e:
                error = ScriptError(e)
                # Sin código del usuario en la traza, es un fallo del paso (p. ej. una tecla que no existe).
                if error.location is None:
                    result.ok, result.error = False, f"{type(e).__name__}: {e}"
                else:
                    result.ok, result.error, result.script_error = False, error.format(), error
            yield result
            if not result.ok:
                return

    def do(self, step: Step, result: Result) -> None:
        handler: Callable[[list[str], Result], None] = getattr(self, f"do_{step.name}")
        handler(step.args, result)

    # Un método `do_<comando>` por comando de `COMMANDS`.

    def do_click(self, a: list[str], r: Result) -> None:
        self.pilot.click(self.key(a[0]))

    def do_click_at(self, a: list[str], r: Result) -> None:
        self.pilot.click_at(float(a[0]), float(a[1]))

    def do_type(self, a: list[str], r: Result) -> None:
        text = " ".join(a).replace("\\n", "\n").replace("\\t", "\t")
        self.pilot.type(text)

    def do_press(self, a: list[str], r: Result) -> None:
        self.pilot.press(a[0])

    def do_focus(self, a: list[str], r: Result) -> None:
        key = self.key(a[0])
        try:
            self.pilot.focus(key)
        except LookupError as e:
            raise StepError(f"no se puede enfocar {key!r}: {e}") from e

    def do_hover(self, a: list[str], r: Result) -> None:
        x, y, w, h = self.rect(a[0])
        self.pilot.move_to(x + w / 2, y + h / 2)

    def do_move(self, a: list[str], r: Result) -> None:
        self.pilot.move_to(float(a[0]), float(a[1]))

    def do_leave(self, a: list[str], r: Result) -> None:
        self.pilot.leave()

    def do_scroll(self, a: list[str], r: Result) -> None:
        dx = float(a[2]) if len(a) > 2 else 0.0
        self.pilot.scroll(self.key(a[0]), float(a[1]), dx)

    def do_drag(self, a: list[str], r: Result) -> None:
        self.pilot.drag(self.key(a[0]), float(a[1]), float(a[2]))

    def do_drag_to(self, a: list[str], r: Result) -> None:
        key = self.key(a[0])
        if len(a) == 3:
            self.pilot.drag_to(key, (float(a[1]), float(a[2])))
        else:
            self.pilot.drag_to(key, self.key(a[1]))

    def do_a11y(self, a: list[str], r: Result) -> None:
        value: str | float | None = None
        if len(a) > 2:
            try:
                value = float(a[2])
            except ValueError:
                value = a[2]
        try:
            self.pilot.a11y_action(self.key(a[0]), a[1], value)
        except LookupError as e:
            raise StepError(f"{a[0]!r} no está en el árbol de accesibilidad: {e}") from e

    def do_wait(self, a: list[str], r: Result) -> None:
        left = float(a[0])
        while left > 1e-9:
            dt = min(FRAME, left)
            self.pilot.frame(dt)
            left -= dt

    def do_frame(self, a: list[str], r: Result) -> None:
        for _ in range(int(a[0]) if a else 1):
            self.pilot.frame()

    def do_settle(self, a: list[str], r: Result) -> None:
        self.pilot.settle()

    def do_resize(self, a: list[str], r: Result) -> None:
        self.size = _size(a)
        self.pilot.resize(*self.size)
        r.data["size"] = list(self.size)

    def do_shot(self, a: list[str], r: Result) -> None:
        self.pilot.settle()
        path = Path(a[0])
        if not path.is_absolute():
            path = self.cwd / path
        if not path.parent.is_dir():
            raise StepError(f"no existe la carpeta {path.parent}")
        key = self.key(a[1]) if len(a) > 1 else None
        self.pilot.png(os.fspath(path), key)
        r.output = str(path)
        r.data["path"] = str(path)

    def do_tree(self, a: list[str], r: Result) -> None:
        self.pilot.settle()
        snap = self.snapshot()
        root = snap.root
        if a:
            node = snap.find(a[0])
            if node is None:
                raise StepError(snap.missing(a[0]))
            root = node
        r.output = _tree.format_tree(root)
        r.data["tree"] = root.to_dict()

    def do_expect(self, a: list[str], r: Result) -> None:
        self.pilot.settle()
        snap = self.snapshot()
        what = a[0]
        if what == "text":
            scope = snap.root
            if len(a) == 4:
                node = snap.find(a[3])
                if node is None:
                    raise StepError(snap.missing(a[3]))
                scope = node
            contents = scope.contents()
            if a[1] not in contents:
                where = f" en {a[3]!r}" if len(a) == 4 else ""
                seen = _tree._quote(contents) if contents else "nada"
                raise StepError(f"no se ve el texto {a[1]!r}{where}; hay: {seen}")
            return
        key = a[1]
        node = snap.find(key)
        if what == "missing":
            if node is not None:
                raise StepError(f"{key!r} sigue pintado")
            return
        if what == "focused":
            focused = self.pilot.focused
            if key == "none":
                if focused is not None:
                    raise StepError(f"se esperaba sin foco; lo tiene {focused!r}")
            elif focused != key:
                if node is None:
                    raise StepError(snap.missing(key))
                raise StepError(f"se esperaba el foco en {key!r}; lo tiene {focused!r}")
            return
        if node is None:
            raise StepError(snap.missing(key))
        if what in ("checked", "unchecked") and what not in node.states:
            state = next((s for s in node.states if s in ("checked", "unchecked")), "sin estado checked")
            raise StepError(f"se esperaba {key!r} {what}; está {state}")
        if what == "value":
            got = node.value if node.value is not None else node.contents()
            if got != a[2]:
                raise StepError(f"se esperaba {key!r} = {a[2]!r}; vale {got!r}")

    def rect(self, key: str) -> tuple[float, float, float, float]:
        rect = self.pilot.rect(self.key(key))
        if rect is None:
            raise StepError(self.snapshot().missing(key))
        return rect
