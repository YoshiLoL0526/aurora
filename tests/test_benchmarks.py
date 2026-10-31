"""La suite de `benchmarks/` funciona: cada escenario a escala mínima, para que no se pudra."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "benchmarks"))

import run
from scenarios import SCENARIOS


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
