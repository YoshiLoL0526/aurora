"""Corrige las apps que escribieron los agentes (o las de referencia).

    uv run evals/agentes/corregir.py CARPETA [CARPETA...]

Cada CARPETA tiene una subcarpeta por tarea (`01_login/app.py`…) o es la carpeta `referencia/`
(`01_login.py`…). Por cada app ejecuta `aurora check --strict` (arranca y no tiene avisos de
layout) y `aurora pilot` con el guion de `comprobaciones/` (hace lo que pide la tarea).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
TASKS = sorted(p.stem for p in (HERE / "comprobaciones").glob("*.txt"))


def aurora(*args: str) -> tuple[int, dict | None, str]:
    cmd = [sys.executable, "-m", "aurora", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = None
    return proc.returncode, data, (proc.stdout + proc.stderr).strip()


def app_path(folder: Path, task: str) -> Path:
    nested = folder / task / "app.py"
    return nested if nested.exists() else folder / f"{task}.py"


def grade(app: Path, task: str) -> dict:
    if not app.exists():
        return {"task": task, "runs": False, "warnings": None, "pilot": False, "detail": "no hay app.py"}
    code, data, out = aurora("check", str(app), "--json")
    runs = code != 1
    warnings = len(data.get("warnings", [])) if isinstance(data, dict) else None
    if not runs:
        return {"task": task, "runs": False, "warnings": warnings, "pilot": False, "detail": out[-400:]}
    script = HERE / "comprobaciones" / f"{task}.txt"
    code, data, out = aurora("pilot", str(app), "--script", str(script), "--json")
    detail = ""
    if code != 0:
        failed = [s for s in (data or {}).get("steps", []) if not s.get("ok")]
        detail = json.dumps(failed[0], ensure_ascii=False)[:400] if failed else out[-400:]
    return {"task": task, "runs": True, "warnings": warnings, "pilot": code == 0, "detail": detail}


def main(folders: list[str]) -> int:
    results = {}
    for folder in map(Path, folders):
        rows = [grade(app_path(folder, t), t) for t in TASKS]
        results[str(folder)] = rows
        print(f"\n## {folder}\n")
        print("| Tarea | Pasa | Arranca | Avisos | Comprobación | Detalle |")
        print("|---|---|---|---|---|---|")
        for r in rows:
            ok = lambda b: "✅" if b else "❌"
            r["pass"] = r["runs"] and r["pilot"] and r["warnings"] == 0
            print(
                f"| {r['task']} | {ok(r['pass'])} | {ok(r['runs'])} | {r['warnings']} | {ok(r['pilot'])} "
                f"| {r['detail']} |"
            )
    (HERE / "ultima.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # ty: ignore[unresolved-attribute]
    raise SystemExit(main(sys.argv[1:] or [str(HERE / "referencia")]))
