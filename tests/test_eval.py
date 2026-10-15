"""Tests for the drift check itself.

A checker that has never been seen to fail proves nothing. Each test here takes a
known-good run, breaks it the way real drift shows up, and asserts the checker
notices. Run with:  uv run pytest
"""

import copy
import json
from pathlib import Path

import pytest

from evals.check import evaluate

FIXTURES = Path(__file__).resolve().parent.parent / "evals" / "fixtures"
BASELINE = FIXTURES / "baseline.json"


def good_run():
    return json.loads((FIXTURES / "good_run.json").read_text())


def test_good_run_passes():
    ev = evaluate(good_run(), BASELINE)
    assert ev["verdict"] == "OK", ev


def test_dropped_rule_is_drift():
    # The kind of drift a prompt edit causes: the Analyzer stops mentioning that the fee is taxed.
    run = good_run()
    run["analysis"]["rules"] = [r for r in run["analysis"]["rules"] if r["id"] != "R6"]
    ev = evaluate(run, BASELINE)
    assert ev["verdict"] == "DRIFT"
    assert "rule_recall" in ev["drifted"]
    assert any(m.startswith("G5") for m in ev["missed_rules"])


def test_wrong_expected_value_is_caught():
    # The kind of drift a cheaper model causes: plausible arithmetic, one cent off.
    run = good_run()
    run["tests"]["tests"][1]["expected"]["total"] = 957.09
    ev = evaluate(run, BASELINE)
    assert any("wholesale_california_volume" in w for w in ev["wrong_tests"])


def test_two_wrong_tests_is_drift():
    run = good_run()
    for t in run["tests"]["tests"][:2]:
        t["expected"]["status"] = "H" if t["expected"]["status"] == "A" else "A"
    ev = evaluate(run, BASELINE)
    assert ev["verdict"] == "DRIFT"
    assert "test_accuracy" in ev["drifted"]


def test_invented_line_number_is_caught():
    run = good_run()
    run["analysis"]["rules"][0]["source_lines"] = [412]     # the file has 74 lines
    ev = evaluate(run, BASELINE)
    assert "R1" in ev["bad_citations"]


def test_changed_prompt_is_reported():
    run = copy.deepcopy(good_run())
    run["prompt_hash"] = "something-else"
    ev = evaluate(run, BASELINE)
    assert "prompt files" in ev["changed_since_baseline"]


# ---- the quality gate and the baseline rules ---------------------------------

def test_gate_fails_below_the_floor_even_without_drift(tmp_path):
    # A weak baseline hides a weak run from the drift check. The gate still catches it.
    weak = json.loads(BASELINE.read_text())
    weak["metrics"]["test_accuracy"] = 0.7
    weak_path = tmp_path / "baseline.json"
    weak_path.write_text(json.dumps(weak))
    run = good_run()
    for t in run["tests"]["tests"][:2]:
        t["expected"]["status"] = "H" if t["expected"]["status"] == "A" else "A"
    ev = evaluate(run, weak_path)
    assert ev["verdict"] == "OK"            # 0.8 is not more than 0.10 below 0.7
    assert ev["gate"] == "FAIL"
    assert "test_accuracy" in ev["below_gate"]


def test_changed_prompt_file_is_named(tmp_path):
    base = json.loads(BASELINE.read_text())
    base["prompt_hashes"] = {"AGENTS.md": "aaa", "agents/analyzer.md": "bbb"}
    base_path = tmp_path / "baseline.json"
    base_path.write_text(json.dumps(base))
    run = good_run()
    run["prompt_hashes"] = {"AGENTS.md": "aaa", "agents/analyzer.md": "ccc"}
    ev = evaluate(run, base_path)
    assert "prompt file agents/analyzer.md" in ev["changed_since_baseline"]


def test_changed_model_is_named():
    run = good_run()
    run["models"]["test_writer"] = "claude-sonnet-5-5"
    ev = evaluate(run, BASELINE)
    assert any("model for test_writer" in c for c in ev["changed_since_baseline"])


def test_fake_baseline_is_flagged():
    ev = evaluate(good_run(), BASELINE)      # the fixture baseline is a fake run
    assert any("fake run" in w for w in ev["warnings"])


def test_baseline_refuses_a_failing_run(tmp_path):
    from evals.check import set_baseline
    run = good_run()
    run["analysis"]["rules"][0]["source_lines"] = [412]
    ev = evaluate(run, BASELINE)
    with pytest.raises(ValueError, match="quality gate"):
        set_baseline(run, ev, tmp_path / "baseline.json")


def test_baseline_refuses_a_fake_run_unless_asked(tmp_path):
    from evals.check import set_baseline
    run = good_run()
    ev = evaluate(run, BASELINE)
    with pytest.raises(ValueError, match="fake run"):
        set_baseline(run, ev, tmp_path / "baseline.json")
    set_baseline(run, ev, tmp_path / "baseline.json", allow_fake=True)
    assert (tmp_path / "baseline.json").exists()
