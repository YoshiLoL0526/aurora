"""Suite de benchmarks de Aurora: cuánto cuesta un frame, fase a fase.

    uv run benchmarks/run.py                          # todos los escenarios
    uv run benchmarks/run.py lista_10k --reps 50      # uno solo, más muestras
    uv run benchmarks/run.py arranque                 # solo el arranque
    uv run benchmarks/run.py --json base.json         # guarda los resultados
    uv run benchmarks/run.py --compare base.json      # compara con una medición anterior
    uv run benchmarks/run.py --markdown               # tabla Markdown (resumen de CI)

Cada operación avanza un frame del piloto headless (mismo runtime que la ventana, sin
presentar en pantalla). Se mide el tiempo total del frame y, con `Pilot.stats`, cada fase:
`view` (tu función de vista), `to_spec` (serializar el árbol), `parse` (dicts → Rust), `layout`
y `paint`. Se publica la mediana y el p95 tras unos frames de calentamiento.

`arranque` mide otra cosa: desde `import aurora` hasta el primer frame de una app típica, con
cada muestra en un proceso nuevo (`startup.py`), y lo compara con su objetivo (`STARTUP_TARGET`).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scenarios import SCENARIOS, Bench, Scenario

import aurora

PHASES = ("view", "to_spec", "parse", "style", "layout", "paint")
WARMUP = 3

STARTUP = "arranque"
# Objetivo del arranque (ms, mediana de `total`): de `import aurora` al primer frame de
# `startup.py` (~550 nodos) en la máquina de referencia. Ver benchmarks/README.md.
STARTUP_TARGET = 250.0
STARTUP_SCRIPT = Path(__file__).parent / "startup.py"


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def _summary(samples: list[dict[str, float]]) -> dict[str, float]:
    totals = [s["total"] for s in samples]
    out = {
        "samples": len(samples),
        "median": statistics.median(totals),
        "p95": _percentile(totals, 0.95),
        "min": min(totals),
    }
    for phase in PHASES:
        out[phase] = statistics.median(s[phase] for s in samples)
    return out


class _TimedView:
    """Envuelve la vista para separar `view()` de la serialización dentro del build."""

    def __init__(self, bench: Bench) -> None:
        self.view = bench.app.view
        self.last = 0.0
        bench.app.view = self

    def __call__(self):
        start = time.perf_counter()
        try:
            return self.view()
        finally:
            self.last = (time.perf_counter() - start) * 1000


def _sample(pilot: aurora.Pilot, timed: _TimedView, total: float) -> dict[str, float]:
    stats = pilot.stats
    # Una reconstrucción parcial no llama a la vista: todo su `build` es serializar.
    view = timed.last if stats["rebuilt"] else 0.0
    timed.last = 0.0
    return {
        "total": total,
        "view": view,
        "to_spec": max(0.0, stats["build"] - view),
        "parse": stats["parse"],
        "style": stats["style"],
        "layout": stats["layout"],
        "paint": stats["paint"],
    }


def run_scenario(scenario: Scenario, *, scale: float, reps: int, budget: float) -> dict:
    """Mide un escenario. `budget`: segundos máximos por operación (con al menos 5 muestras)."""
    # Primer frame en frío: árbol nuevo, sin caché de párrafos ni estado de animación.
    cold: list[dict[str, float]] = []
    nodes = 0
    for _ in range(max(1, min(3, reps))):
        bench = scenario.make(scale)
        timed = _TimedView(bench)
        start = time.perf_counter()
        pilot = bench.app.pilot()
        cold.append(_sample(pilot, timed, (time.perf_counter() - start) * 1000))
        nodes = pilot.stats["nodes"]

    if bench.setup:
        bench.setup(pilot)
    ops = {"cold": _summary(cold)}
    for name, op in bench.ops.items():
        for _ in range(WARMUP):
            op(pilot)
        samples: list[dict[str, float]] = []
        deadline = time.perf_counter() + budget
        while len(samples) < reps and (len(samples) < 5 or time.perf_counter() < deadline):
            start = time.perf_counter()
            op(pilot)
            samples.append(_sample(pilot, timed, (time.perf_counter() - start) * 1000))
        ops[name] = _summary(samples)
    return {"description": scenario.description, "nodes": nodes, **bench.info, "ops": ops}


def run_startup(*, reps: int) -> dict:
    """Mide el arranque: cada muestra lanza `startup.py` en un proceso nuevo."""
    samples: dict[str, list[dict[str, float]]] = {"import": [], "primer_frame": [], "total": []}
    nodes = 0
    for _ in range(max(3, min(reps, 10))):
        out = subprocess.run(
            [sys.executable, str(STARTUP_SCRIPT)], capture_output=True, text=True, check=True
        )
        data = json.loads(out.stdout.strip().splitlines()[-1])
        nodes = data["nodes"]
        for op, field_ in (("import", "import"), ("primer_frame", "frame"), ("total", "total")):
            samples[op].append({"total": data[field_], **dict.fromkeys(PHASES, 0.0)})
    return {
        "description": "Desde import aurora hasta el primer frame de una app típica",
        "nodes": nodes,
        "target": STARTUP_TARGET,
        "ops": {op: _summary(s) for op, s in samples.items()},
    }


def startup_verdict(results: dict) -> str | None:
    """Línea con el arranque frente a su objetivo (si se midió)."""
    res = results.get(STARTUP)
    if res is None:
        return None
    median = res["ops"]["total"]["median"]
    mark = "✅" if median <= res["target"] else "⚠️"
    return f"{mark} arranque: {median:.0f} ms de mediana (objetivo ≤ {res['target']:.0f} ms)"


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def metadata(scale: float) -> dict:
    return {
        "aurora": aurora.__version__,
        "commit": _git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpus": os.cpu_count(),
        "scale": scale,
        "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


# ---------------------------------------------------------------------- salida


def _delta(now: float, before: float | None) -> str:
    if not before:
        return ""
    pct = (now - before) / before * 100
    mark = "▲" if pct > 10 else "▼" if pct < -10 else "≈"
    return f"{mark}{pct:+.0f}%"


def _rows(results: dict, baseline: dict | None) -> list[list[str]]:
    rows = []
    for name, res in results.items():
        base_ops = (baseline or {}).get(name, {}).get("ops", {})
        for i, (op, s) in enumerate(res["ops"].items()):
            before = base_ops.get(op, {}).get("median")
            rows.append(
                [
                    f"{name} ({res['nodes']} nodos)" if i == 0 else "",
                    op,
                    f"{s['median']:.2f}",
                    f"{s['p95']:.2f}",
                    *(f"{s[p]:.2f}" for p in PHASES),
                    _delta(s["median"], before) if baseline else "",
                ]
            )
    return rows


HEADER = ["escenario", "op", "mediana", "p95", *PHASES, "vs base"]


def format_table(results: dict, baseline: dict | None = None) -> str:
    rows = [HEADER, *_rows(results, baseline)]
    if not baseline:
        rows = [r[:-1] for r in rows]
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = []
    for i, r in enumerate(rows):
        cells = (c.ljust(w) if j < 2 else c.rjust(w) for j, (c, w) in enumerate(zip(r, widths, strict=True)))
        lines.append("  ".join(cells))
        if i == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)


def format_markdown(results: dict, meta: dict, baseline: dict | None = None) -> str:
    rows = [HEADER, *_rows(results, baseline)]
    if not baseline:
        rows = [r[:-1] for r in rows]
    out = [
        f"### Benchmarks de Aurora {meta['aurora']} ({meta['commit'] or 'sin commit'})",
        "",
        f"{meta['platform']} · Python {meta['python']} · {meta['cpus']} CPU · tiempos en ms por frame",
        "",
        "| " + " | ".join(rows[0]) + " |",
        "|" + "|".join(["---", "---", *["---:"] * (len(rows[0]) - 2)]) + "|",
    ]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    names = [STARTUP, *(s.name for s in SCENARIOS)]
    parser = argparse.ArgumentParser(description="Suite de benchmarks de Aurora (ms por frame).")
    parser.add_argument("scenarios", nargs="*", help=f"por defecto, todos: {', '.join(names)}")
    parser.add_argument("--reps", type=int, default=30, help="muestras por operación (máximo)")
    parser.add_argument("--budget", type=float, default=3.0, help="segundos máximos por operación")
    parser.add_argument("--scale", type=float, default=1.0, help="tamaño de los escenarios (1 = el nominal)")
    parser.add_argument("--json", type=Path, help="guarda los resultados en este archivo")
    parser.add_argument("--compare", type=Path, help="JSON de una ejecución anterior con la que comparar")
    parser.add_argument("--markdown", action="store_true", help="imprime una tabla Markdown")
    args = parser.parse_args(argv)
    if unknown := set(args.scenarios) - set(names):
        parser.error(f"escenario desconocido: {', '.join(sorted(unknown))} (hay: {', '.join(names)})")

    baseline = json.loads(args.compare.read_text(encoding="utf-8"))["results"] if args.compare else None
    chosen = [s for s in SCENARIOS if not args.scenarios or s.name in args.scenarios]
    results = {}
    if not args.scenarios or STARTUP in args.scenarios:
        print(f"· {STARTUP}: de import aurora al primer frame…", file=sys.stderr, flush=True)
        results[STARTUP] = run_startup(reps=args.reps)
    for scenario in chosen:
        print(f"· {scenario.name}: {scenario.description}…", file=sys.stderr, flush=True)
        results[scenario.name] = run_scenario(scenario, scale=args.scale, reps=args.reps, budget=args.budget)

    meta = metadata(args.scale)
    if args.json:
        args.json.write_text(json.dumps({"meta": meta, "results": results}, indent=2), encoding="utf-8")
    if args.markdown:
        print(format_markdown(results, meta, baseline))
    else:
        print(format_table(results, baseline))
    if verdict := startup_verdict(results):
        print()
        print(verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
