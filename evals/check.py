"""Evaluate a run: a QUALITY GATE against a fixed bar, and a DRIFT CHECK against a baseline.

Two different questions, deliberately kept apart:

    Quality gate   Is this run good enough to use?       Compared with fixed floors (GATE).
    Drift check    Is this run worse than before?         Compared with a reviewed baseline run.

A run can pass the gate and still drift (it got worse but is still above the bar),
or fail the gate without drifting (the baseline was already that bad). You want both.

The four metrics, each between 0 and 1:

    rule_recall      share of the golden rules (evals/golden.json, written by a person
                     from the code) that the Analyzer found
    citations_valid  share of extracted rules whose cited line numbers exist in the source
    test_accuracy    share of tests whose expected output matches the ORACLE
                     (evals/oracle.py: what the legacy code really returns)
    enough_tests     1 if at least MIN_TESTS tests came back, else 0

Drift = a metric fell more than TOLERANCE below the baseline. The report also says what
changed since the baseline: which prompt files, which models, or nothing. That decides
where you look first: your edit, the model choice, or the provider and the input.

Every check is deterministic: keywords and arithmetic, no model judging a model. The
same output always gets the same score, so a score change means the OUTPUT changed.

Score a finished run:
    uv run python -m evals.check runs/<run_id>/result.json
Accept a reviewed, good run as the new baseline:
    uv run python -m evals.check runs/<run_id>/result.json --set-baseline

Called by: run.py at the end of every run; tests/test_eval.py
Calls:     evals/oracle.py (price) for every generated test
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

from evals.oracle import price

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "golden.json"
BASELINE = HERE / "baseline.json"
MIN_TESTS = 8

# Drift: how far below the baseline a metric may fall before it counts.
TOLERANCE = 0.10      # one missed rule out of 8 is a 0.125 drop, so it trips

# Quality gate: the floor each metric must reach, whatever the baseline says.
GATE = {
    "rule_recall": 0.875,     # at most one golden rule missed (keyword matching can miss a rephrasing)
    "citations_valid": 1.0,   # an invented line number is never acceptable
    "test_accuracy": 0.9,     # at most one test in ten disagrees with the oracle
    "enough_tests": 1.0,
}


def evaluate(result, baseline_path=BASELINE):
    """Score one run. Returns a dict; report() turns it into text.

    Keeping scoring and printing apart lets the tests check the numbers directly.
    """
    analysis = result.get("analysis") or {}
    rules = analysis.get("rules", [])
    tests = (result.get("tests") or {}).get("tests", [])

    # 1. Did the Analyzer find every rule a human found?
    rule_texts = [" ".join(str(r.get(k, "")) for k in ("description", "condition", "action")).lower()
                  for r in rules]
    golden = json.loads(GOLDEN.read_text())["rules"]
    missed = [g["id"] + " " + g["what"] for g in golden
              if not any(matches(text, g["keywords"]) for text in rule_texts)]

    # 2. Does every cited line exist? A citation past the end of the file is invented.
    last_line = result["source_line_count"]
    bad_citations = [r.get("id", "?") for r in rules
                     if not r.get("source_lines")
                     or not all(isinstance(n, int) and 1 <= n <= last_line for n in r["source_lines"])]

    # 3. Is every test's expected output what the legacy code really returns?
    #    The model's expected value is a CLAIM. The oracle decides.
    wrong_tests = []
    for t in tests:
        try:
            total, status = price(t["inputs"])
            claimed_total = Decimal(str(t["expected"]["total"]))
            claimed_status = t["expected"]["status"]
        except (KeyError, ValueError, TypeError, ArithmeticError) as err:
            wrong_tests.append(f"{t.get('name', '?')}: malformed ({err})")
            continue
        if abs(claimed_total - total) > Decimal("0.005") or claimed_status != status:
            wrong_tests.append(f"{t.get('name', '?')}: says {claimed_total} {claimed_status}, legacy gives {total} {status}")

    metrics = {
        "rule_recall": round(1 - len(missed) / len(golden), 3),
        "citations_valid": round(1 - len(bad_citations) / len(rules), 3) if rules else 0.0,
        "test_accuracy": round(1 - len(wrong_tests) / len(tests), 3) if tests else 0.0,
        "enough_tests": 1.0 if len(tests) >= MIN_TESTS else 0.0,
    }

    # 4. Quality gate: absolute floors.
    below_gate = [m for m, floor in GATE.items() if metrics[m] < floor]

    # 5. Drift check: compare with the baseline.
    warnings = []
    if not Path(baseline_path).exists():
        # First ever run: nothing to compare with yet, so the run is its own baseline.
        baseline = {"metrics": metrics, "prompt_hash": result.get("prompt_hash"), "models": result.get("models")}
        warnings.append("no baseline yet: drift cannot be measured until one is set")
    else:
        baseline = json.loads(Path(baseline_path).read_text())
        if str(baseline.get("run_id", "")).endswith("-fake"):
            warnings.append(f"the baseline ({baseline['run_id']}) is a fake run; it says nothing about "
                            "the real model. Review a real run and set it as the baseline")
    drift = [m for m, value in metrics.items() if value < baseline["metrics"][m] - TOLERANCE]

    return {
        "verdict": "DRIFT" if drift else "OK",
        "gate": "FAIL" if below_gate else "PASS",
        "metrics": metrics,
        "baseline": baseline["metrics"],
        "baseline_run": baseline.get("run_id", "(none)"),
        "drifted": drift,
        "below_gate": below_gate,
        "changed_since_baseline": what_changed(result, baseline),
        "missed_rules": missed,
        "bad_citations": bad_citations,
        "wrong_tests": wrong_tests,
        "warnings": warnings,
    }


def what_changed(result, baseline):
    """Name what is different from the baseline run: prompt files, models, or nothing.

    Per-file hashes name the exact file. Older records only have the combined hash,
    which can say 'prompt files' but not which one.
    """
    changed = []
    now, then = result.get("prompt_hashes"), baseline.get("prompt_hashes")
    if now and then:
        files = sorted(f for f in set(now) | set(then) if now.get(f) != then.get(f))
        changed += [f"prompt file {f}" for f in files]
    elif result.get("prompt_hash") != baseline.get("prompt_hash"):
        changed.append("prompt files")
    for agent, model in (result.get("models") or {}).items():
        before = (baseline.get("models") or {}).get(agent)
        if model != before:
            changed.append(f"model for {agent}: {before} -> {model}")
    return changed or ["nothing: same prompts, same models (so look at the provider's model or the input)"]


def matches(text, keywords):
    """True if text holds every keyword group. A group that is a list needs any one word."""
    for group in keywords:
        options = group if isinstance(group, list) else [group]
        if not any(word.lower() in text for word in options):
            return False
    return True


def report(ev):
    lines = [
        f"QUALITY GATE  {ev['gate']}    (fixed floors in evals/check.py GATE)",
        f"DRIFT CHECK   {ev['verdict']}    (against baseline run {ev['baseline_run']})",
        f"  {'metric':<16}{'this run':>9}{'floor':>8}{'baseline':>10}",
    ]
    for m, value in ev["metrics"].items():
        flags = []
        if m in ev["below_gate"]:
            flags.append("BELOW FLOOR")
        if m in ev["drifted"]:
            flags.append("DRIFT")
        flag = ("  <-- " + ", ".join(flags)) if flags else ""
        lines.append(f"  {m:<16}{value:>9}{GATE[m]:>8}{ev['baseline'][m]:>10}{flag}")
    lines.append(f"  changed since baseline: {'; '.join(ev['changed_since_baseline'])}")
    for label in ("missed_rules", "bad_citations", "wrong_tests"):
        for item in ev[label]:
            lines.append(f"  {label}: {item}")
    for w in ev["warnings"]:
        lines.append(f"  WARNING: {w}")
    return "\n".join(lines)


def set_baseline(result, ev, baseline_path=BASELINE, allow_fake=False):
    """Record a run as the known-good reference future runs are compared with.

    A baseline is a REVIEWED good run, so two kinds of run are refused: one that fails
    the quality gate, and a fake run (unless allow_fake), whose scores say nothing about
    the real model.
    """
    if ev["gate"] != "PASS":
        raise ValueError(f"refusing: run {result['run_id']} fails the quality gate on {ev['below_gate']}")
    if result["run_id"].endswith("-fake") and not allow_fake:
        raise ValueError(f"refusing: {result['run_id']} is a fake run. Pass --allow-fake if you mean it")
    Path(baseline_path).write_text(json.dumps({
        "run_id": result["run_id"],
        "prompt_hash": result["prompt_hash"],
        "prompt_hashes": result.get("prompt_hashes"),
        "models": result["models"],
        "metrics": ev["metrics"],
    }, indent=2) + "\n")
    print(f"Baseline set from run {result['run_id']}")


if __name__ == "__main__":
    result = json.loads(Path(sys.argv[1]).read_text())
    ev = evaluate(result)
    print(report(ev))
    if "--set-baseline" in sys.argv:
        try:
            set_baseline(result, ev, allow_fake="--allow-fake" in sys.argv)
        except ValueError as err:
            print(err)
            sys.exit(1)
