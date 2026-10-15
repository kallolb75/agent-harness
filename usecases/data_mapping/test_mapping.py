"""Tests for the data mapping use case. Run with:  uv run pytest usecases"""

from decimal import Decimal

import pytest

from usecases.data_mapping.fake import FakeClient, mapping
from usecases.data_mapping.mapping import (CONTROL, GOLDEN, SOURCE, evaluate, reconcile,
                                           run_agent, run_tool)


def fresh_state():
    return {"mapping": None, "reconciled": False, "submitted": False}


def test_fake_run_reconciles_submits_and_matches_the_data_owner():
    summary, state, spent = run_agent(FakeClient())
    agreed, _ = evaluate(state)
    assert state["reconciled"] and state["submitted"]
    assert agreed == len(GOLDEN)


def test_reconciliation_catches_a_balance_left_in_cents():
    passed, lines = reconcile(mapping("copy"))
    assert not passed
    assert any(line.startswith("FAIL balance_total") for line in lines)


def test_the_golden_mapping_reconciles():
    passed, lines = reconcile(GOLDEN)
    assert passed, lines


def test_submit_is_refused_before_reconciliation_passes():
    state = fresh_state()
    run_tool("propose_mapping", {"mapping": mapping("copy")}, state)
    run_tool("reconcile", {}, state)
    output, is_error = run_tool("submit_mapping", {}, state)
    assert is_error and output.startswith("Refused")
    assert not state["submitted"]


def test_a_transform_outside_the_list_is_refused():
    bad = mapping("cents_to_dollars")
    bad[5]["transform"] = "lambda v: v / 100"          # the model may not supply code
    output, is_error = run_tool("propose_mapping", {"mapping": bad}, fresh_state())
    assert is_error and "not allowed" in output


def test_personal_data_is_masked_in_the_samples():
    output, _ = run_tool("get_source_schema", {}, fresh_state())
    assert "SMITH" not in output and "19650412" not in output


def test_control_totals_match_the_source_data():
    # Guards the test data itself: the control report must agree with the legacy rows.
    assert Decimal(sum(r["BAL_AMT"] for r in SOURCE["rows"])) / 100 == Decimal(CONTROL["total_balance_dollars"])


def test_the_turn_cap_stops_the_loop():
    with pytest.raises(RuntimeError, match="within 3 turns"):
        run_agent(FakeClient(), max_turns=3)
