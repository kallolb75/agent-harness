"""Tests for the portfolio triage use case. Run with:  uv run pytest usecases"""

import pytest

from usecases.portfolio_triage.fake import FakeClient
from usecases.portfolio_triage.triage import APPS, evaluate, run_agent, run_tool


def test_fake_run_decides_every_app_and_agrees_with_the_architect():
    summary, decisions, spent = run_agent(FakeClient())
    agreed, coverage, _ = evaluate(decisions)
    assert coverage == 1.0
    assert agreed == len(APPS)
    assert spent > 0


def test_a_disposition_outside_the_list_is_refused_in_code():
    decisions = {}
    output, is_error = run_tool("record_decision",
                                {"name": "HR-REPORTS", "disposition": "decommission", "reason": "x"},
                                decisions)
    assert is_error and "Invalid disposition" in output
    assert decisions == {}


def test_the_answer_key_is_never_shown_to_the_agent():
    output, is_error = run_tool("get_app", {"name": "ORDER-ENTRY"}, {})
    assert not is_error
    assert "expected" not in output


def test_the_budget_stops_the_next_call():
    # The first fake call costs about $0.0021; a $0.001 budget must stop the second call.
    with pytest.raises(RuntimeError, match="budget"):
        run_agent(FakeClient(), budget_usd=0.001)


def test_the_turn_cap_stops_the_loop():
    with pytest.raises(RuntimeError, match="within 2 turns"):
        run_agent(FakeClient(), max_turns=2)
