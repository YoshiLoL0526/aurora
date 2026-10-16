"""Hot reload: al guardar un archivo de la app, la vista se reconstruye con el
código nuevo sin cerrar la ventana y sin perder el estado.

Se activa con `App(view, reload=True)`, la variable de entorno
`AURORA_RELOAD=1` o `aurora dev app.py`. Un hilo vigila el script principal y
los módulos locales que importa (los que están en su carpeta, fuera de
`site-packages`); cuando uno cambia, el siguiente frame:

1. Compila los archivos cambiados (un error de sintaxis no toca nada).
2. Vuelve a ejecutar, en su propio diccionario, cada módulo cambiado, los
   módulos locales que usan algo suyo y el script principal (siempre: es el
   que crea la `App`). Ahí `App(...)` y `app.run()` no abren nada: la `App`
   nueva solo presta su `view` y su `theme` a la que ya está en marcha.
3. Conserva los `Signal`: cada `Signal` del código nuevo que esté en el mismo
   sitio que uno del anterior (una variable global, un atributo o un elemento
   de un objeto propio, de un dict o de una lista) se sustituye por el antiguo,
   que guarda su valor y su identidad: los hilos, las corrutinas y los módulos
   que no se recargan siguen usando el mismo. Si el valor ya no es del mismo
   tipo que el inicial nuevo, gana el nuevo.

Si la recarga o la vista fallan, se muestra el error en la ventana (y en la
consola) y los módulos vuelven a como estaban; al guardar de nuevo se reintenta.
Los `Signal` locales (creados dentro de una función) no se conservan.
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
from collections.abc import Iterator
from pathlib import Path
from types import BuiltinFunctionType, FunctionType, MethodType, ModuleType
from typing import Any

from . import _core
from .elements import Element, column, scroll, text
from .signal import Signal

# Cada cuánto se miran las fechas de modificación (s).
INTERVAL = 0.3
# Profundidad máxima a la que se buscan `Signal` dentro de objetos y contenedores.
DEPTH = 4

_PACKAGE = Path(__file__).resolve().parent


def enabled(flag: bool | None) -> bool:
    """`flag` si se indica; si no, la variable de entorno `AURORA_RELOAD`."""
    if flag is not None:
        return flag
    return os.environ.get("AURORA_RELOAD", "").strip().lower() in ("1", "true", "yes", "on")


class _Context(threading.local):
    """Recarga en curso: las `App` que se crean y ejecutan no abren ventana."""

    active = False
    created: Any = None
    ran: Any = None


context = _Context()


class ReloadError(Exception):
    """Fallo al recargar: el traceback ya formateado está en `details`."""

    def __init__(self, details: str) -> None:
        super().__init__(details.strip().splitlines()[-1] if details.strip() else "error al recargar")
        self.details = details


def _stamp(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return st.st_mtime_ns, st.st_size


def _excluded(path: Path) -> bool:
    if path.is_relative_to(_PACKAGE):
        return True
    if any(part in ("site-packages", "dist-packages") for part in path.parts):
        return True
    prefixes = {Path(p).resolve() for p in (sys.prefix, sys.base_prefix, sys.exec_prefix)}
    return any(path.is_relative_to(p) for p in prefixes)


class Reloader:
    """Vigila los archivos de la app y aplica los cambios en el hilo de la interfaz."""

    def __init__(self, main: ModuleType) -> None:
        file = getattr(main, "__file__", None)
        if not file:
            raise ValueError("el hot reload necesita que la app se ejecute desde un archivo")
        self.main = main
        self.path = Path(file).resolve()
        self.root = self.path.parent
        self.error: str | None = None
        self._lock = threading.Lock()
        self._paths: dict[str, Path | None] = {}
        self._stamps: dict[Path, tuple[int, int] | None] = {}
        self._changed: set[Path] = set()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        for path in self.files():
            self._stamps[path] = _stamp(path)

    # --- Vigilancia -------------------------------------------------------

    def modules(self) -> dict[Path, ModuleType]:
        """Módulos de la app que se pueden recargar, por archivo (el principal incluido)."""
        found: dict[Path, ModuleType] = {}
        for module in list(sys.modules.values()):
            file = getattr(module, "__file__", None)
            if isinstance(file, str) and (path := self._local(file)) is not None:
                found[path] = module
        found[self.path] = self.main
        return found

    def _local(self, file: str) -> Path | None:
        """Ruta del archivo si es código de la app (memorizado: se mira cada `INTERVAL`)."""
        if file not in self._paths:
            path = Path(file).resolve() if file.endswith(".py") else None
            ok = path is not None and path.is_relative_to(self.root) and not _excluded(path)
            self._paths[file] = path if ok else None
        return self._paths[file]

    def files(self) -> list[Path]:
        return list(self.modules())

    def check(self) -> bool:
        """Compara las fechas de modificación; si hay cambios pendientes, pide un frame y devuelve `True`."""
        with self._lock:
            for path in self.files():
                stamp = _stamp(path)
                if path not in self._stamps:
                    self._stamps[path] = stamp  # módulo importado tras la última recarga
                elif stamp != self._stamps[path]:
                    self._stamps[path] = stamp
                    self._changed.add(path)
            changed = bool(self._changed)
        if changed:
            _core.wake()
        return changed

    @property
    def pending(self) -> bool:
        return bool(self._changed)

    def start(self) -> None:
        """Arranca el hilo que vigila los archivos y despierta la ventana si cambian."""
        if self._thread is not None:
            return

        def watch() -> None:
            while not self._stop.wait(INTERVAL):
                self.check()

        self._thread = threading.Thread(target=watch, name="aurora-reload", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # --- Recarga ----------------------------------------------------------

    def apply(self) -> Any:
        """Recarga lo que cambió. Devuelve la `App` creada por el script (o `None`).

        Lanza `ReloadError` si algo falla; en ese caso los módulos quedan como estaban.
        """
        with self._lock:
            changed, self._changed = self._changed, set()
        modules = self.modules()
        targets = _affected({p: modules[p] for p in changed if p in modules}, modules)
        # Primero las dependencias: un módulo entra en `sys.modules` antes que los que importa.
        order = [m for m in reversed(list(sys.modules.values())) if m in targets and m is not self.main]
        order.append(self.main)

        try:
            codes = [(m, _compile(m)) for m in order]
        except Exception as e:
            raise ReloadError(_format(e)) from None

        snapshots: list[tuple[ModuleType, dict[str, Any]]] = []
        context.active, context.created, context.ran = True, None, None
        try:
            for module, code in codes:
                snapshots.append((module, dict(module.__dict__)))
                exec(code, module.__dict__)
            app = context.ran or context.created
        except BaseException as e:
            for module, old in reversed(snapshots):
                module.__dict__.clear()
                module.__dict__.update(old)
            if not isinstance(e, Exception):
                raise
            raise ReloadError(_format(e)) from None
        finally:
            context.active, context.created, context.ran = False, None, None

        local = {m.__name__ for m in self.modules().values()}
        for module, old in snapshots:
            keep_signals(old, module.__dict__, local)
        return app


def _format(error: BaseException) -> str:
    """Traceback sin los frames de la recarga: empieza en el código de la app."""
    tb = error.__traceback__
    while tb is not None and tb.tb_frame.f_code.co_filename == __file__:
        tb = tb.tb_next
    return "".join(traceback.format_exception(type(error), error, tb))


def _compile(module: ModuleType) -> Any:
    path = Path(module.__file__ or "")
    return compile(path.read_bytes(), str(path), "exec")


def _affected(changed: dict[Path, ModuleType], modules: dict[Path, ModuleType]) -> set[ModuleType]:
    """Los módulos cambiados y los módulos locales que usan algo suyo (transitivamente)."""
    affected = set(changed.values())
    names = {m.__name__ for m in affected}
    grew = True
    while grew:
        grew = False
        for module in modules.values():
            if module in affected:
                continue
            for value in list(module.__dict__.values()):
                uses = value in affected if isinstance(value, ModuleType) else _owner(value) in names
                if uses:
                    affected.add(module)
                    names.add(module.__name__)
                    grew = True
                    break
    return affected


def _owner(value: Any) -> str | None:
    try:
        owner = getattr(value, "__module__", None)
    except Exception:
        return None
    return owner if isinstance(owner, str) else None


# --- Conservar los Signal ---------------------------------------------------

Step = tuple[str, Any]  # ("item", clave) o ("attr", nombre)

_OPAQUE = (type, ModuleType, FunctionType, BuiltinFunctionType, MethodType, str, bytes, int, float)


def _children(obj: Any, local: set[str]) -> Iterator[tuple[Step, Any]]:
    """Dónde puede haber `Signal` dentro de `obj`: contenedores y objetos de la app."""
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if isinstance(k, (str, int)):
                yield ("item", k), v
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield ("item", i), v
    elif not isinstance(obj, _OPAQUE) and type(obj).__module__ in local:
        attrs = getattr(obj, "__dict__", None)
        if isinstance(attrs, dict):
            for k, v in list(attrs.items()):
                yield ("attr", k), v
        for cls in type(obj).__mro__:
            for name in getattr(cls, "__slots__", ()):
                if hasattr(obj, name) and name != "__dict__":
                    yield ("attr", name), getattr(obj, name)


def _signals(namespace: dict[str, Any], local: set[str]) -> dict[tuple[Step, ...], tuple[Any, Step, Signal]]:
    """Cada `Signal` alcanzable desde un módulo, por su camino: `camino -> (contenedor, paso, signal)`."""
    found: dict[tuple[Step, ...], tuple[Any, Step, Signal]] = {}
    seen: set[int] = set()

    def walk(container: Any, step: Step, value: Any, path: tuple[Step, ...], depth: int) -> None:
        if isinstance(value, Signal):
            found.setdefault(path, (container, step, value))
            return
        if depth == 0 or id(value) in seen:
            return
        seen.add(id(value))
        for child_step, child in _children(value, local):
            walk(value, child_step, child, (*path, child_step), depth - 1)

    for name, value in list(namespace.items()):
        if not name.startswith("__"):
            walk(namespace, ("item", name), value, (("item", name),), DEPTH)
    return found


def _compatible(old: Any, new: Any) -> bool:
    if old is None or new is None:
        return True
    a, b = type(old), type(new)
    # Clases redefinidas al recargar: misma clase aunque no sea el mismo objeto.
    return a is b or (a.__module__, a.__qualname__) == (b.__module__, b.__qualname__)


def _put(container: Any, step: Step, value: Any) -> bool:
    kind, key = step
    try:
        if kind == "item":
            if isinstance(container, tuple):
                return False
            container[key] = value
        else:
            object.__setattr__(container, key, value)
    except Exception:
        return False
    return True


def keep_signals(old: dict[str, Any], new: dict[str, Any], local: set[str] | None = None) -> int:
    """Pone en el espacio de nombres `new` los `Signal` de `old` que están en el mismo sitio.

    El `Signal` antiguo se queda con las suscripciones del nuevo (las del código que se acaba de
    ejecutar). Donde no se puede sustituir (una tupla), se copia el valor. Devuelve cuántos conservó.
    """
    if local is None:
        local = {v for v in (old.get("__name__"), new.get("__name__")) if isinstance(v, str)}
    before = _signals(old, local)
    kept = 0
    for path, (container, step, signal) in _signals(new, local).items():
        previous = before.get(path)
        if previous is None:
            continue
        prev = previous[2]
        if prev is signal or not _compatible(prev._value, signal._value):
            continue
        if _put(container, step, prev):
            prev._subscribers = signal._subscribers
        else:
            signal._value = prev._value
        kept += 1
    return kept


# --- Pantalla de error ------------------------------------------------------


MONOSPACE = {"win32": "Consolas", "darwin": "Menlo"}.get(sys.platform, "DejaVu Sans Mono")


def error_view(details: str) -> Element:
    """Lo que se ve cuando la recarga o la vista fallan: el traceback y cómo seguir."""
    lines = details.rstrip().splitlines() or ["Error desconocido"]
    return column(key="aurora:reload-error", grow=1, padding=28, gap=14, bg="#1A1014", color="#F5E8EA")[
        text("Error en el código", size=20, weight=700, color="#FF8A9A"),
        text(lines[-1], size=14, weight=600),
        text(
            "Corrige el código y guarda: la app se recarga sola, sin perder el estado.",
            size=12,
            color="#C9A9AF",
        ),
        scroll(grow=1, bg="#120B0E", radius=8, border_color="#3A2228", border_width=1, padding=14)[
            text(
                "\n".join(lines),
                size=12,
                line_height=1.45,
                font_family=MONOSPACE,
                color="#E6CED3",
            ),
        ],
    ]
