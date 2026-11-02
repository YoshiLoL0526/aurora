"""La suite de `benchmarks/` funciona: cada escenario a escala mínima, para que no se pudra."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "benchmarks"))

import run
from scenarios import FRAME, SCENARIOS


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_scenario_measures_every_op(scenario):
    result = run.run_scenario(scenario, scale=0.01, reps=2, budget=0.0)
    assert result["nodes"] > 0
    assert set(result["ops"]) == {"cold", *scenario.make(0.01).ops}
    for summary in result["ops"].values():
        assert summary["samples"] >= 1
        assert summary["median"] > 0
        assert all(summary[p] >= 0 for p in run.PHASES)
    # El frame en frío siempre reconstruye: tiene que haber coste de Python y de parseo.
    assert result["ops"]["cold"]["parse"] > 0


def test_cli_writes_json_and_compares(tmp_path, capsys):
    out = tmp_path / "base.json"
    args = ["dashboard_50", "--scale", "0.05", "--reps", "2", "--budget", "0"]
    assert run.main([*args, "--json", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["meta"]["aurora"]
    assert "rebuild" in data["results"]["dashboard_50"]["ops"]

    assert run.main([*args, "--compare", str(out), "--markdown"]) == 0
    printed = capsys.readouterr().out
    assert "| dashboard_50" in printed
    assert "vs base" in printed


def test_cli_rejects_unknown_scenario():
    with pytest.raises(SystemExit):
        run.main(["no_existe"])


def test_startup_is_measured_against_its_target():
    result = run.run_startup(reps=1)
    assert result["nodes"] > 0 and result["target"] == run.STARTUP_TARGET
    assert set(result["ops"]) == {"import", "primer_frame", "total"}
    ops = result["ops"]
    assert ops["total"]["samples"] == 3
    assert 0 < ops["import"]["median"] < ops["total"]["median"]
    assert "objetivo" in (run.startup_verdict({run.STARTUP: result}) or "")


def test_budgets_name_real_ops():
    for scenario in SCENARIOS:
        bench = scenario.make(0.01)
        assert set(bench.budgets) <= set(bench.ops), scenario.name
        assert all(ms > 0 for ms in bench.budgets.values())
    # Las operaciones interactivas de la suite tienen presupuesto de 60 fps.
    assert any(ms == FRAME for s in SCENARIOS for ms in s.make(0.01).budgets.values())


def test_frame_verdict_counts_ops_over_budget():
    results = {
        "x": {
            "ops": {
                "cold": {"median": 90.0, "p95": 95.0},
                "hover": {"median": 2.0, "p95": 3.0, "budget": FRAME},
                "scroll": {"median": 20.0, "p95": 25.0, "budget": FRAME},
            }
        }
    }
    lines, over = run.frame_verdict(results)
    assert over == 1
    assert lines[0].startswith("60 fps: 1 de 2")
    assert any(line.startswith("❌ x scroll") for line in lines)
    assert "escala 1" in run.frame_verdict(results, 0.1)[0][0]


def test_slack_tolerates_ops_over_budget_within_the_margin():
    results = {
        "x": {
            "ops": {
                "hover": {"median": 2.0, "p95": 3.0, "budget": FRAME},
                "scroll": {"median": 20.0, "p95": 25.0, "budget": FRAME},
                "drag": {"median": 30.0, "p95": 35.0, "budget": FRAME},
            }
        }
    }
    lines, over = run.frame_verdict(results, slack=1.5)
    # 20 ms se pasa de 16,7 pero cabe en 25: se avisa sin fallar; 30 ms falla.
    assert over == 1
    assert lines[0].startswith("60 fps: 1 de 3")
    assert "--slack 1.5" in lines[0]
    assert any(line.startswith("⚠️ x scroll") for line in lines)
    assert any(line.startswith("❌ x drag") for line in lines)
    with pytest.raises(SystemExit):
        run.main(["x", "--slack", "0.5"])


def test_check_fails_when_an_op_is_over_budget(monkeypatch, capsys):
    import scenarios

    original = scenarios.dashboard_50

    def tight(scale: float = 1.0):
        bench = original(scale)
        bench.budgets = {"hover": 1e-6}
        return bench

    monkeypatch.setattr(
        run, "SCENARIOS", [scenarios.Scenario("dashboard_50", "con un presupuesto imposible", tight)]
    )
    args = ["dashboard_50", "--scale", "0.05", "--reps", "2", "--budget", "0"]
    assert run.main(args) == 0  # sin --check solo se informa
    assert run.main([*args, "--check"]) == 1
    assert "❌ dashboard_50 hover" in capsys.readouterr().out
