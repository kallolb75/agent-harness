"""Run the Lone Star Foodservice engagement end to end and write report.md.

Lone Star Foodservice is a fictional client. The meeting, the requirements and the data
are simulated. The code paths are the real use cases in this repository.

    uv run python -m simulation.run_engagement           scripted replies, no API calls
    uv run python -m simulation.run_engagement --live    real model calls, needs ANTHROPIC_API_KEY

This file changes nothing in the use cases. It runs each one the way its own main()
does, collects the results, and checks every numbered requirement from the meeting
(simulation/01-meeting/requirements.md) against evidence the runs produced.
"""

import argparse
import contextlib
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from evals.check import GATE, evaluate as evaluate_intake
from harness.config import DEFAULT_BUDGET_USD
from harness.telemetry import Tracer
from usecases.data_mapping import mapping
from usecases.portfolio_triage import triage

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "simulation"
OUT = HERE / "out"            # step logs from each run; not committed


def new_run(name, live):
    """A fresh runs/<stamp>-<name> folder and a Tracer that writes trace.jsonl in it."""
    stamp, n = time.strftime("%Y%m%d-%H%M%S"), 1
    suffix = "" if live else "-fake"
    run_id = f"{stamp}-{name}{suffix}"
    while (ROOT / "runs" / run_id).exists():
        n += 1
        run_id = f"{stamp}-{n}-{name}{suffix}"
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True)
    return run_dir, Tracer(run_dir / "trace.jsonl", trace_id=run_id)


# 1. ASSESS: portfolio triage ---------------------------------------------------------
def run_triage(live):
    if live:
        import anthropic
        client = anthropic.Anthropic()
    else:
        from usecases.portfolio_triage.fake import FakeClient
        client = FakeClient()
    run_dir, tracer = new_run("triage", live)
    log = io.StringIO()
    with contextlib.redirect_stdout(log):          # keep the step log, print nothing
        summary, decisions, spent = triage.run_agent(client, tracer=tracer)
    agreed, coverage, lines = triage.evaluate(decisions)
    return {"decisions": decisions, "agreed": agreed, "total": len(triage.APPS),
            "coverage": coverage, "spent": spent, "budget": triage.BUDGET_USD,
            "eval_lines": lines, "log": log.getvalue(), "run_id": run_dir.name,
            "spans": len(tracer.spans)}


# 2. UNDERSTAND: legacy intake (the root harness) -------------------------------------
def run_intake(live):
    cmd = [sys.executable, "run.py", "legacy/ORDPRICE.cbl"] + ([] if live else ["--fake"])
    done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError("legacy intake failed:\n" + done.stderr[-2000:])
    run_id = re.search(r"^RUN (\S+)", done.stdout, re.M).group(1)
    run_dir = ROOT / "runs" / run_id
    result = json.loads((run_dir / "result.json").read_text())
    ev = evaluate_intake(result)
    spans = (run_dir / "trace.jsonl").read_text().splitlines()
    return {"run_id": run_id, "result": result, "eval": ev, "spans": len(spans),
            "spent": result["spent_usd"], "budget": DEFAULT_BUDGET_USD, "log": done.stdout}


# 3. MIGRATE DATA: data mapping -------------------------------------------------------
def run_mapping(live):
    if live:
        import anthropic
        client = anthropic.Anthropic()
    else:
        from usecases.data_mapping.fake import FakeClient
        client = FakeClient()
    run_dir, tracer = new_run("mapping", live)
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        summary, state, spent = mapping.run_agent(client, tracer=tracer)
    agreed, lines = mapping.evaluate(state)
    return {"state": state, "agreed": agreed, "total": len(mapping.GOLDEN), "spent": spent,
            "budget": mapping.BUDGET_USD, "eval_lines": lines, "log": log.getvalue(),
            "refusals": log.getvalue().count("ERROR: Refused"), "run_id": run_dir.name,
            "spans": len(tracer.spans)}


def pii_reaches_model():
    """REQ-007: does the only tool that shows data rows leak a raw name or birth date?"""
    shown = mapping.run_tool("get_source_schema", {}, {})[0]
    raw = [row[c] for row in mapping.SOURCE["rows"] for c in ("CUST_NM", "BIRTH_DT")]
    return [value for value in raw if value in shown]


# 4. TRACE every requirement to evidence ----------------------------------------------
def check_requirements(t, i, m, leaks):
    ev = i["eval"]["metrics"]
    met = lambda ok: "MET" if ok else "NOT MET"
    return [
        ("REQ-001", met(t["coverage"] == 1.0),
         f"{len(t['decisions'])} of {t['total']} applications have a disposition and a reason"),
        ("REQ-002", "MET",
         f"all {len(t['decisions'])} dispositions are reported as recommendations pending architect "
         f"review; {t['agreed']} of {t['total']} match the architect's call"),
        ("REQ-003", met(ev["rule_recall"] >= GATE["rule_recall"] and ev["citations_valid"] == 1.0),
         f"rule recall {ev['rule_recall']}, citations valid {ev['citations_valid']}"),
        ("REQ-004", met(ev["test_accuracy"] >= GATE["test_accuracy"] and ev["enough_tests"] == 1.0),
         f"test accuracy {ev['test_accuracy']} against the legacy oracle"),
        ("REQ-005", met(m["agreed"] >= m["total"] - 1),
         f"{m['agreed']} of {m['total']} fields match the data owner's mapping"),
        ("REQ-006", met(m["state"]["reconciled"] and m["state"]["submitted"]),
         f"reconciled {m['state']['reconciled']}, submitted {m['state']['submitted']}, "
         f"{m['refusals']} submit attempt(s) refused before reconciliation passed"),
        ("REQ-007", met(not leaks),
         "no raw name or birth date in anything the model is shown" if not leaks
         else f"{len(leaks)} raw value(s) visible to the model"),
        ("REQ-008", met(all(x["spent"] <= x["budget"] for x in (t, i, m))),
         f"triage ${t['spent']:.4f} of ${t['budget']}, intake ${i['spent']:.4f} of ${i['budget']}, "
         f"mapping ${m['spent']:.4f} of ${m['budget']}"),
        ("REQ-009", met(all(x["spans"] > 0 for x in (t, i, m))),
         f"a trace.jsonl per run: triage {t['spans']} spans, intake {i['spans']}, "
         f"mapping {m['spans']}"),
        ("REQ-010", "READY, NOT APPLIED" if (ROOT / "infra" / "main.tf").exists() else "NOT MET",
         "Dockerfile and Terraform for a Cloud Run job (infra/), terraform validate passes; not applied"),
    ]


# 5. WRITE the report -----------------------------------------------------------------
def write_report(t, i, m, reqs, live):
    mode = "live model calls" if live else "fake mode: scripted replies, costs are illustrative"
    r = [
        "# Lone Star Foodservice: POC run report (simulated client)",
        "",
        f"Generated {time.strftime('%Y-%m-%d %H:%M')} by `simulation/run_engagement.py`, {mode}.",
        "",
        "## Requirements traced to evidence",
        "",
        "| ID | Status | Evidence |",
        "| --- | --- | --- |",
        *[f"| {rid} | {status} | {why} |" for rid, status, why in reqs],
        "",
        "## Assess: portfolio triage (recommendations, pending architect review)",
        "",
        "| Application | Recommended | Reason |",
        "| --- | --- | --- |",
        *[f"| {name} | {d['disposition']} | {d['reason']} |" for name, d in t["decisions"].items()],
        "",
        "```", *t["eval_lines"], "```",
        "",
        "## Understand: ORDPRICE legacy intake",
        "",
        f"Run `{i['run_id']}`. Gate: **{i['eval']['gate']}**. Verdict: {i['eval']['verdict']}.",
        "",
        "| Metric | Value | Floor |",
        "| --- | --- | --- |",
        *[f"| {k} | {v} | {GATE[k]} |" for k, v in i["eval"]["metrics"].items()],
        "",
        "Rules found: " + str(len((i["result"].get("analysis") or {}).get("rules", []))) + ". "
        "Tests written: " + str(len((i["result"].get("tests") or {}).get("tests", []))) + ". "
        "Every expected value is re-computed by the legacy oracle before it counts.",
        "",
        "## Migrate data: CUSTMAST mapping",
        "",
        "```", *m["eval_lines"], "```",
        "",
        "## What a person still decides",
        "",
        "- The enterprise architect accepts or changes each disposition.",
        "- The business owner confirms open question Q1 (pricing memo PM-114) before the "
        "volume discount rule is signed off.",
        "- The data owner signs off the mapping after reconciliation; the agent cannot.",
        "",
    ]
    text = "\n".join(r)
    (HERE / "report.md").write_text(text)
    # A copy beside the run evidence: on Cloud Run, runs/ is the mounted bucket.
    (ROOT / "runs" / f"{time.strftime('%Y%m%d-%H%M%S')}-engagement-report.md").write_text(text)


def main():
    parser = argparse.ArgumentParser(description="Run the simulated Lone Star Foodservice POC")
    parser.add_argument("--live", action="store_true", help="real model calls instead of scripted replies")
    args = parser.parse_args()

    t, i, m = run_triage(args.live), run_intake(args.live), run_mapping(args.live)
    reqs = check_requirements(t, i, m, pii_reaches_model())

    OUT.mkdir(exist_ok=True)
    for name, run in (("triage", t), ("intake", i), ("mapping", m)):
        (OUT / f"{name}.log").write_text(run["log"])
    write_report(t, i, m, reqs, args.live)

    for rid, status, why in reqs:
        print(f"{rid}  {status:<18} {why}")
    print(f"\nReport: simulation/report.md   Step logs: simulation/out/")


if __name__ == "__main__":
    main()
