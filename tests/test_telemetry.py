"""Tests for telemetry: every step is a span, spans nest the way the calls nest,
and failures are recorded rather than lost.

Offline, against the scripted replies in fake/.
"""

from types import SimpleNamespace

import pytest

from harness.llm import LLM, BudgetExceeded
from harness.orchestrator import run_orchestrator
from harness.telemetry import Tracer, load, render_tree, summarize


def fresh_state():
    return {"source_name": "ORDPRICE.cbl", "source": "   1| fake source", "analyzer_runs": 0}


def traced_run(tmp_path, budget=1.00):
    tracer = Tracer(tmp_path / "trace.jsonl", trace_id="test-run")
    llm = LLM(tmp_path, budget_usd=budget, fake=True, tracer=tracer)
    with tracer.span("run"):
        run_orchestrator(fresh_state(), llm, max_turns=6)
    return llm, load(tmp_path / "trace.jsonl")


def test_one_span_per_model_call_matching_the_ledger(tmp_path):
    llm, spans = traced_run(tmp_path)
    calls = [s for s in spans if s["name"] == "llm.call"]
    assert len(calls) == len(llm.rows) == 5
    assert abs(summarize(spans)["cost_usd"] - llm.spent_usd) < 1e-6


def test_spans_nest_the_way_the_calls_nest(tmp_path):
    _, spans = traced_run(tmp_path)
    by_id = {s["span_id"]: s for s in spans}

    def chain(span):
        names = []
        while span:
            names.append(span["name"])
            span = by_id.get(span["parent_id"])
        return names

    analyzer_call = next(s for s in spans if s["name"] == "llm.call" and s["attrs"]["agent"] == "analyzer")
    assert chain(analyzer_call) == ["llm.call", "worker.attempt", "worker", "tool.call",
                                    "orchestrator.turn", "run"]
    orchestrator_call = next(s for s in spans if s["name"] == "llm.call" and s["attrs"]["agent"] == "orchestrator")
    assert chain(orchestrator_call) == ["llm.call", "orchestrator.turn", "run"]


def test_budget_stop_is_recorded_as_an_error_span(tmp_path):
    tracer = Tracer(tmp_path / "trace.jsonl")
    llm = LLM(tmp_path, budget_usd=0.005, fake=True, tracer=tracer)
    with pytest.raises(BudgetExceeded):
        run_orchestrator(fresh_state(), llm, max_turns=6)
    spans = load(tmp_path / "trace.jsonl")
    # The refused call is the innermost error; every span it bubbled up through is
    # marked as an error too, so the tree shows the whole path the failure took.
    refused = [s for s in spans if s["status"] == "error" and s["name"] == "llm.call"]
    assert len(refused) == 1
    assert "BudgetExceeded" in refused[0]["attrs"]["error"]
    assert "input_tokens" not in refused[0]["attrs"]      # stopped BEFORE the call


def test_tree_view_shows_every_call(tmp_path):
    _, spans = traced_run(tmp_path)
    tree = render_tree(spans)
    assert tree.count("llm.call") == 5
    assert "tool.call run_analyzer" in tree and "tool.call run_test_writer" in tree


def test_reply_cut_off_at_max_tokens_is_not_treated_as_finished(tmp_path):
    llm = LLM(tmp_path, budget_usd=1.00, fake=True)
    cut_off = SimpleNamespace(
        stop_reason="max_tokens",
        content=[SimpleNamespace(type="text", text="Intake compl")],
        usage=SimpleNamespace(input_tokens=900, output_tokens=1000,
                              cache_creation_input_tokens=0, cache_read_input_tokens=0),
    )
    llm._fake_response = lambda agent: cut_off
    with pytest.raises(RuntimeError, match="cut off at max_tokens"):
        run_orchestrator(fresh_state(), llm, max_turns=6)
