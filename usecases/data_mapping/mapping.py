"""Use case: data mapping and reconciliation (the Migrate data phase).

The job: move a legacy customer table into a new schema. The agent reads both
schemas, proposes a field-by-field mapping, and must PROVE the mapping by
reconciliation against the legacy system's own control totals before it may submit.

    uv run python -m usecases.data_mapping.mapping --fake    offline: scripted replies, no key, no cost
    uv run python -m usecases.data_mapping.mapping           real run: needs ANTHROPIC_API_KEY

The same five parts as portfolio triage:
    1. the loop       call the model, run the tools it asks for, send the results back
    2. tools          what the agent may do, and the code that does it
    3. guardrails     a turn cap, a budget cap, every tool input checked in code
    4. telemetry      one line per model call and per tool call, with tokens and cost
    5. an eval        the agent's mapping compared with the one a data owner signed off

What this use case adds:
    * The agent checks its own work with a deterministic tool, reconcile(), and must
      fix the mapping until reconciliation passes. Submitting before that is refused.
    * The agent never writes code. It picks transforms from a fixed list of small,
      tested functions, so nothing the model writes ever runs on the data.
    * The agent sees the schemas and two masked sample rows, never the full table.
"""

import argparse
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

MODEL = "claude-sonnet-5-5"
PRICE_PER_MILLION = {"input": 2.00, "output": 10.00}   # USD per million tokens; re-check before quoting
MAX_TURNS = 10                                         # guardrail: the loop can never run forever
BUDGET_USD = 0.25                                      # guardrail: checked before every model call

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "data.json").read_text())
SOURCE = DATA["source"]            # the legacy table: column descriptions and rows
TARGET = DATA["target"]            # the new schema
CONTROL = DATA["control_totals"]   # the legacy system's own totals for this extract
GOLDEN = DATA["golden_mapping"]    # the data owner's mapping: never shown to the agent

SYSTEM = (
    "You are a data migration engineer. Map every field of the target table to a source "
    "column and one transform from the allowed list. Then call reconcile to prove the "
    "mapping against the legacy control totals. If reconciliation fails, read why, fix the "
    "mapping and reconcile again. Submit only after reconciliation passes, then reply with a "
    "short summary."
)


# The ONLY transforms the agent may use. Each is a small function a person wrote and
# tested. The model chooses by name; it never supplies code.
def _name_part(value, part):
    last, _, first = value.partition(",")
    return (first if part == "first" else last).strip().title() or None


TRANSFORMS = {
    "copy":             lambda v: v,
    "to_int":           lambda v: int(v),
    "name_first":       lambda v: _name_part(v, "first"),
    "name_last":        lambda v: _name_part(v, "last"),
    "date_yyyymmdd":    lambda v: datetime.strptime(v, "%Y%m%d").date().isoformat(),
    "cents_to_dollars": lambda v: Decimal(v) / 100,
    "status_code":      lambda v: {"A": "active", "I": "inactive", "C": "closed"}.get(v),
}


# 2. TOOLS ---------------------------------------------------------------------------
TOOLS = [
    {"name": "get_source_schema",
     "description": "The legacy table: each column with its description, the row count, "
                    "and two sample rows with personal data masked.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_target_schema",
     "description": "The new table: each field with its type and whether it is required.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "propose_mapping",
     "description": "Store a complete mapping: one entry per target field, naming a source "
                    "column and a transform. Replaces any earlier mapping.",
     "input_schema": {"type": "object", "properties": {"mapping": {"type": "array", "items": {
         "type": "object",
         "properties": {"target": {"type": "string"}, "source": {"type": "string"},
                        "transform": {"type": "string", "enum": list(TRANSFORMS)}},
         "required": ["target", "source", "transform"]}}},
         "required": ["mapping"]}},
    {"name": "reconcile",
     "description": "Migrate every row with the stored mapping and compare the result with "
                    "the legacy control totals: row count, total balance, status counts, and "
                    "no missing required values.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "submit_mapping",
     "description": "Submit the stored mapping for sign-off. Only allowed after it has passed "
                    "reconciliation.",
     "input_schema": {"type": "object", "properties": {}}},
]


def mask(column, value):
    """Hide personal data in the samples while keeping its format visible."""
    if column == "CUST_NM":
        return ", ".join(part[0] + "*" * (len(part) - 1) for part in value.split(", "))
    if column == "BIRTH_DT":
        return value[:4] + "****"
    return value


def migrate(mapping):
    """Apply the mapping to every source row. A transform that fails gives None."""
    rows = []
    for source_row in SOURCE["rows"]:
        row = {}
        for m in mapping:
            try:
                row[m["target"]] = TRANSFORMS[m["transform"]](source_row[m["source"]])
            except (ValueError, TypeError, KeyError, ArithmeticError):
                row[m["target"]] = None
        rows.append(row)
    return rows


def reconcile(mapping):
    """The deterministic check. Returns (passed, one line per check)."""
    rows = migrate(mapping)
    checks = []

    count_ok = len(rows) == CONTROL["row_count"]
    checks.append((count_ok, f"row_count {len(rows)} vs control {CONTROL['row_count']}"))

    try:
        total = sum(Decimal(str(r.get("balance") or 0)) for r in rows)
    except ArithmeticError:
        total = None
    expected = Decimal(CONTROL["total_balance_dollars"])
    checks.append((total == expected, f"balance_total {total} vs control {expected}"))

    statuses = dict(Counter(r.get("status") for r in rows))
    checks.append((statuses == CONTROL["status_counts"],
                   f"status_counts {statuses} vs control {CONTROL['status_counts']}"))

    required = [f for f, spec in TARGET["fields"].items() if spec["required"]]
    missing = [f"{f} in row {i + 1}" for i, r in enumerate(rows) for f in required if r.get(f) is None]
    checks.append((not missing, f"required_fields missing: {missing or 'none'}"))

    passed = all(ok for ok, _ in checks)
    lines = [("ok   " if ok else "FAIL ") + text for ok, text in checks]
    return passed, lines


def run_tool(name, args, state):
    """Run one tool the model asked for. Returns (text for the model, is_error).

    The model only ASKS. Every check below is a guardrail in code (3).
    """
    if name == "get_source_schema":
        samples = [{c: mask(c, v) for c, v in row.items()} for row in SOURCE["rows"][:2]]
        return json.dumps({"table": SOURCE["table"], "columns": SOURCE["columns"],
                           "row_count": len(SOURCE["rows"]), "sample_rows_masked": samples}), False

    if name == "get_target_schema":
        return json.dumps(TARGET), False

    if name == "propose_mapping":
        mapping = args.get("mapping") or []
        targets = [m.get("target") for m in mapping]
        problems = []
        if sorted(targets) != sorted(TARGET["fields"]):
            problems.append(f"map every target field exactly once: {list(TARGET['fields'])}")
        for m in mapping:
            if m.get("source") not in SOURCE["columns"]:
                problems.append(f"unknown source column {m.get('source')}")
            if m.get("transform") not in TRANSFORMS:
                problems.append(f"transform {m.get('transform')} is not allowed; use one of {list(TRANSFORMS)}")
        if problems:
            return "Mapping refused: " + "; ".join(problems), True
        state["mapping"] = mapping
        state["reconciled"] = False          # a new mapping must be proved again
        return f"Mapping stored: {len(mapping)} fields. Call reconcile to prove it.", False

    if name == "reconcile":
        if not state["mapping"]:
            return "No mapping stored yet. Call propose_mapping first.", True
        passed, lines = reconcile(state["mapping"])
        state["reconciled"] = passed
        return ("PASS. " if passed else "FAIL. ") + "; ".join(lines), False

    if name == "submit_mapping":
        if not state["reconciled"]:
            return "Refused: the stored mapping has not passed reconciliation.", True
        state["submitted"] = True
        return "Mapping submitted for data owner sign-off.", False

    return f"Unknown tool {name}.", True


# 1. THE LOOP ------------------------------------------------------------------------
def run_agent(client, max_turns=MAX_TURNS, budget_usd=BUDGET_USD):
    """Call the model, run the tools it asks for, send the results back, repeat.

    Returns (final text, state, dollars spent).
    """
    messages = [{"role": "user", "content": f"Map {SOURCE['table']} to {TARGET['table']}."}]
    state = {"mapping": None, "reconciled": False, "submitted": False}
    spent = 0.0

    for turn in range(1, max_turns + 1):
        if spent >= budget_usd:                                    # 3. guardrail: budget
            raise RuntimeError(f"budget spent: ${spent:.4f} of ${budget_usd}")

        response = client.messages.create(model=MODEL, max_tokens=2000, system=SYSTEM,
                                          tools=TOOLS, messages=messages)

        usage = response.usage                                     # 4. telemetry: tokens and cost
        cost = (usage.input_tokens * PRICE_PER_MILLION["input"]
                + usage.output_tokens * PRICE_PER_MILLION["output"]) / 1_000_000
        spent += cost
        print(f"turn {turn}: model  {usage.input_tokens:>5} in {usage.output_tokens:>4} out  "
              f"${cost:.4f}  stop={response.stop_reason}")

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "max_tokens":                   # 3. guardrail: cut-off reply
            raise RuntimeError("reply cut off at max_tokens")
        if response.stop_reason != "tool_use":                     # done: no more tool requests
            text = "".join(block.text for block in response.content if block.type == "text")
            return text, state, spent

        results = []
        for block in response.content:
            if block.type == "tool_use":
                output, is_error = run_tool(block.name, block.input, state)
                print(f"        tool   {block.name}  ->  {'ERROR: ' if is_error else ''}{output[:110]}")
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": output, "is_error": is_error})
        messages.append({"role": "user", "content": results})

    raise RuntimeError(f"no answer within {max_turns} turns")      # 3. guardrail: turn cap


# 5. THE EVAL ------------------------------------------------------------------------
def evaluate(state):
    """Compare the agent's mapping with the data owner's. Deterministic: same input, same score.

    Returns (fields that agree, one report line per field).
    """
    chosen = {m["target"]: m for m in (state["mapping"] or [])}
    agreed, lines = 0, []
    for g in GOLDEN:
        m = chosen.get(g["target"], {})
        got = f"{m.get('source', '-')} {m.get('transform', '-')}"
        owner = f"{g['source']} {g['transform']}"
        same = m.get("source") == g["source"] and m.get("transform") == g["transform"]
        agreed += same
        lines.append(f"  {g['target']:<12}agent: {got:<28}owner: {owner:<28}"
                     f"{'agree' if same else 'DIFFERENT'}")
    return agreed, lines


def main():
    parser = argparse.ArgumentParser(description="Data mapping and reconciliation agent")
    parser.add_argument("--fake", action="store_true", help="replay scripted replies, no API calls")
    args = parser.parse_args()

    if args.fake:
        from usecases.data_mapping.fake import FakeClient
        client = FakeClient()
    else:
        import anthropic
        client = anthropic.Anthropic()             # reads ANTHROPIC_API_KEY from the environment

    summary, state, spent = run_agent(client)
    print(f"\n{summary}\n")

    agreed, lines = evaluate(state)
    gate = "PASS" if state["submitted"] and state["reconciled"] and agreed >= len(GOLDEN) - 1 else "FAIL"
    print(f"EVAL  {gate}: reconciled {state['reconciled']}, submitted {state['submitted']}, "
          f"{agreed} of {len(GOLDEN)} fields agree with the data owner, ${spent:.4f} spent")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
