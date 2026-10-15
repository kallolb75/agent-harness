"""Run the harness on one legacy program, then score the run.

    uv run run.py legacy/ORDPRICE.cbl --fake           offline, no key, no cost
    uv run run.py legacy/ORDPRICE.cbl --fake --trace   same, and print every call as it happens
    uv run run.py legacy/ORDPRICE.cbl                  real run, needs ANTHROPIC_API_KEY
    uv run run.py legacy/ORDPRICE.cbl --budget 0.10    tighter cap

What happens, in order (docs/CALL_FLOW.md draws it):
    1. prepare   number the source lines, create the run folder, the state and the tracer
    2. intake    run_orchestrator() loops: the orchestrator model calls the workers as tools
    3. record    write result.json: what the agents produced, plus fingerprints for drift
    4. evaluate  evals/check.py scores the run (quality gate) and compares it with the
                 baseline (drift check)

Everything a run produces lands in runs/<run_id>/:
    tokens.jsonl   one priced line per model call            (the cost ledger)
    trace.jsonl    one span per step, nested as a tree        (telemetry)
    result.json    the agents' outputs and the fingerprints   (input to the eval)
"""

import argparse
import json
import time
from pathlib import Path

from evals.check import evaluate, report
from harness.config import AGENT_NAMES, DEFAULT_BUDGET_USD, MAX_ORCHESTRATOR_TURNS
from harness.context import load_agent, prompt_hash, prompt_hashes
from harness.llm import LLM, BudgetExceeded
from harness.orchestrator import run_orchestrator
from harness.telemetry import Tracer, load, render_tree, summarize


def main():
    parser = argparse.ArgumentParser(description="Legacy code intake harness")
    parser.add_argument("source", help="path to the COBOL program")
    parser.add_argument("--fake", action="store_true", help="replay scripted replies, no API calls")
    parser.add_argument("--budget", type=float, default=DEFAULT_BUDGET_USD, help="USD cap for this run")
    parser.add_argument("--trace", action="store_true", help="print every step as it happens")
    args = parser.parse_args()

    # 1. PREPARE ----------------------------------------------------------------
    run_id = time.strftime("%Y%m%d-%H%M%S") + ("-fake" if args.fake else "")
    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True)

    source_path = Path(args.source)
    source_lines = source_path.read_text().splitlines()
    # Number every line so agents can cite them and the eval can check the citations.
    numbered = "\n".join(f"{i:>4}| {line}" for i, line in enumerate(source_lines, start=1))

    # STATE is the shared blackboard. Workers write their full outputs here;
    # the orchestrator only ever sees one-line summaries of it.
    state = {"source_name": source_path.name, "source": numbered, "analyzer_runs": 0}

    tracer = Tracer(run_dir / "trace.jsonl", trace_id=run_id, echo=args.trace)
    llm = LLM(run_dir, args.budget, fake=args.fake, tracer=tracer)

    with tracer.span("run", source=source_path.name, fake=args.fake, budget_usd=args.budget) as run_span:
        # 2. INTAKE --------------------------------------------------------------
        try:
            summary = run_orchestrator(state, llm, MAX_ORCHESTRATOR_TURNS)
        except BudgetExceeded as err:
            # A stopped run is still a recorded run: what was produced, and what it cost.
            summary = f"STOPPED: {err}"
        except RuntimeError as err:
            # Turn cap hit, a reply cut off, or a worker that never returned valid JSON.
            # Record it and score whatever was produced; the trace shows where it failed.
            summary = f"FAILED: {err}"

        # 3. RECORD --------------------------------------------------------------
        result = {
            "run_id": run_id,
            "source": source_path.name,
            "source_line_count": len(source_lines),
            "prompt_hash": prompt_hash(),
            "prompt_hashes": prompt_hashes(),
            "models": {name: load_agent(name)["model"] for name in AGENT_NAMES},
            "analyzer_runs": state["analyzer_runs"],
            "spent_usd": round(llm.spent_usd, 6),
            "summary": summary,
            "analysis": state.get("analysis"),
            "tests": state.get("tests"),
        }
        (run_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")

        # 4. EVALUATE ------------------------------------------------------------
        with tracer.span("eval") as eval_span:
            ev = evaluate(result)
            eval_span.set(verdict=ev["verdict"], gate=ev["gate"], metrics=ev["metrics"])
        run_span.set(spent_usd=round(llm.spent_usd, 6), verdict=ev["verdict"], gate=ev["gate"])

    print(f"\nRUN {run_id}\n")
    print(summary + "\n")
    print(llm.cost_table() + "\n")
    print(report(ev) + "\n")
    spans = load(run_dir / "trace.jsonl")
    print(render_tree(spans))
    print(f"\nFiles: {run_dir}/result.json, {run_dir}/tokens.jsonl, {run_dir}/trace.jsonl")
    if summarize(spans)["errors"]:
        print("Errors recorded in the trace: " + "; ".join(summarize(spans)["errors"]))


if __name__ == "__main__":
    main()
