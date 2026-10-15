"""Tests for the harness controls: the budget cap, the order rule, the turn cap.

These run offline against the scripted replies in fake/, so they cost nothing.
"""

import pytest

from harness.llm import LLM, BudgetExceeded
from harness.orchestrator import dispatch, run_orchestrator


def fresh_state():
    return {"source_name": "ORDPRICE.cbl", "source": "   1| fake source", "analyzer_runs": 0}


def test_full_fake_run_produces_analysis_and_tests(tmp_path):
    state = fresh_state()
    summary = run_orchestrator(state, LLM(tmp_path, budget_usd=1.00, fake=True), max_turns=6)
    assert "Intake complete" in summary
    assert len(state["analysis"]["rules"]) == 9
    assert len(state["tests"]["tests"]) == 10


def test_budget_stops_the_run(tmp_path):
    # The analyzer's fake call costs about $0.012. A $0.005 cap must stop the run
    # before the next call, not after the money is gone.
    llm = LLM(tmp_path, budget_usd=0.005, fake=True)
    with pytest.raises(BudgetExceeded):
        run_orchestrator(fresh_state(), llm, max_turns=6)
    assert llm.spent_usd < 0.005 + 0.02   # overshoot is at most one call


def test_test_writer_refused_before_analyzer(tmp_path):
    state = fresh_state()
    reply = dispatch("run_test_writer", {}, state, LLM(tmp_path, budget_usd=1.00, fake=True))
    assert reply.startswith("Refused")
    assert "tests" not in state


def test_third_analyzer_run_refused(tmp_path):
    state = fresh_state()
    llm = LLM(tmp_path, budget_usd=1.00, fake=True)
    dispatch("run_analyzer", {}, state, llm)
    dispatch("run_analyzer", {"focus": "2000-VOLUME-DISCOUNT"}, state, llm)
    reply = dispatch("run_analyzer", {"focus": "again"}, state, llm)
    assert reply.startswith("Refused")
    assert state["analyzer_runs"] == 2


def test_turn_cap_stops_a_loop(tmp_path):
    with pytest.raises(RuntimeError, match="did not finish"):
        run_orchestrator(fresh_state(), LLM(tmp_path, budget_usd=1.00, fake=True), max_turns=2)


def test_every_call_is_logged(tmp_path):
    llm = LLM(tmp_path, budget_usd=1.00, fake=True)
    run_orchestrator(fresh_state(), llm, max_turns=6)
    lines = (tmp_path / "tokens.jsonl").read_text().splitlines()
    assert len(lines) == 5                     # 3 orchestrator turns + analyzer + test writer
    assert abs(llm.spent_usd - sum(r["cost_usd"] for r in llm.rows)) < 1e-6
