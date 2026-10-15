"""A minimal agent harness: one agent, three tools, guardrails, telemetry and an eval.

The job: an architect hands over an application inventory. The agent reads each
application, recommends a modernization disposition (retain, retire, rehost,
replatform, repurchase or refactor) with a one-sentence reason, and records it.

    uv run python -m usecases.portfolio_triage.triage --fake    offline: scripted replies, no key, no cost
    uv run python -m usecases.portfolio_triage.triage           real run: needs ANTHROPIC_API_KEY

Everything a harness needs is in this one file, in five numbered parts:
    1. the loop       call the model, run the tools it asks for, send the results back
    2. tools          what the agent may do, and the code that does it
    3. guardrails     a turn cap, a budget cap, and every tool input checked in code
    4. telemetry      one line per model call and per tool call, with tokens and cost
    5. an eval        the agent's decisions compared with a human architect's
"""

import argparse
import json
from pathlib import Path

MODEL = "claude-sonnet-5-5"
PRICE_PER_MILLION = {"input": 2.00, "output": 10.00}   # USD per million tokens; re-check before quoting
MAX_TURNS = 8                                          # guardrail: the loop can never run forever
BUDGET_USD = 0.25                                      # guardrail: checked before every model call
DISPOSITIONS = ["retain", "retire", "rehost", "replatform", "repurchase", "refactor"]

HERE = Path(__file__).resolve().parent
APPS = json.loads((HERE / "apps.json").read_text())["apps"]

SYSTEM = (
    "You are a modernization architect. For every application in the inventory, choose one "
    f"disposition from {DISPOSITIONS} and record it with a one-sentence reason a CIO would accept. "
    "Read each application's details before deciding. When every application has a decision, "
    "reply with a short summary."
)


# 2. TOOLS ---------------------------------------------------------------------------
# What the model is told it can do: a name, a description (read as an instruction)
# and a JSON Schema for the input.
TOOLS = [
    {"name": "list_apps",
     "description": "List the names of every application in the inventory.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_app",
     "description": "Get one application's details: technology, age, users, how often it changes, "
                    "business value and notes.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}},
                      "required": ["name"]}},
    {"name": "record_decision",
     "description": "Record the disposition for one application with a one-sentence reason. "
                    "Call it once per application.",
     "input_schema": {"type": "object",
                      "properties": {"name": {"type": "string"},
                                     "disposition": {"type": "string", "enum": DISPOSITIONS},
                                     "reason": {"type": "string"}},
                      "required": ["name", "disposition", "reason"]}},
]


def run_tool(name, args, decisions):
    """Run one tool the model asked for. Returns (text for the model, is_error).

    The model only ASKS. This function decides. Every check below is a guardrail
    in code (3): a prompt can ask the model to behave, only code can make it.
    """
    apps = {app["name"]: app for app in APPS}

    if name == "list_apps":
        return json.dumps(list(apps)), False

    if name == "get_app":
        app = apps.get(args.get("name"))
        if app is None:
            return f"No application named {args.get('name')}.", True
        details = {k: v for k, v in app.items() if k != "expected"}   # never show the answer key
        return json.dumps(details), False

    if name == "record_decision":
        app, choice, reason = args.get("name"), args.get("disposition"), args.get("reason")
        if app not in apps:
            return f"No application named {app}.", True
        if choice not in DISPOSITIONS:
            return f"Invalid disposition {choice}. Choose one of {DISPOSITIONS}.", True
        if app in decisions:
            return f"{app} already has a decision: {decisions[app]['disposition']}.", True
        if not reason:
            return "A reason is required.", True
        decisions[app] = {"disposition": choice, "reason": reason}
        return f"Recorded {app}: {choice}. {len(decisions)} of {len(apps)} decided.", False

    return f"Unknown tool {name}.", True


# 1. THE LOOP ------------------------------------------------------------------------
def run_agent(client, max_turns=MAX_TURNS, budget_usd=BUDGET_USD):
    """Call the model, run the tools it asks for, send the results back, repeat.

    Returns (final text, decisions, dollars spent).
    """
    messages = [{"role": "user", "content": "Triage the application inventory."}]
    decisions = {}
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

        # Keep the model's turn, tool requests included. The API keeps no memory,
        # so this list is the whole conversation and is sent again every turn.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "max_tokens":                   # 3. guardrail: cut-off reply
            raise RuntimeError("reply cut off at max_tokens")
        if response.stop_reason != "tool_use":                     # done: no more tool requests
            text = "".join(block.text for block in response.content if block.type == "text")
            return text, decisions, spent

        # The model may ask for several tools in one turn. Run each one and send all
        # the results back together, each tagged with the id of the request it answers.
        results = []
        for block in response.content:
            if block.type == "tool_use":
                output, is_error = run_tool(block.name, block.input, decisions)
                print(f"        tool   {block.name} {json.dumps(block.input)[:55]}  ->  "
                      f"{'ERROR: ' if is_error else ''}{output[:60]}")
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": output, "is_error": is_error})
        messages.append({"role": "user", "content": results})

    raise RuntimeError(f"no answer within {max_turns} turns")      # 3. guardrail: turn cap


# 5. THE EVAL ------------------------------------------------------------------------
def evaluate(decisions):
    """Compare the agent's decisions with the architect's. Deterministic: same input, same score.

    Returns (how many agree, share of apps decided, one report line per app).
    """
    agreed, lines = 0, []
    for app in APPS:
        got = decisions.get(app["name"], {}).get("disposition", "(none)")
        same = got == app["expected"]
        agreed += same
        lines.append(f"  {app['name']:<16}agent: {got:<12}architect: {app['expected']:<12}"
                     f"{'agree' if same else 'DIFFERENT'}")
    return agreed, len(decisions) / len(APPS), lines


def main():
    parser = argparse.ArgumentParser(description="Application portfolio triage agent")
    parser.add_argument("--fake", action="store_true", help="replay scripted replies, no API calls")
    args = parser.parse_args()

    if args.fake:
        from usecases.portfolio_triage.fake import FakeClient         # same .messages.create() as the real client
        client = FakeClient()
    else:
        import anthropic
        client = anthropic.Anthropic()             # reads ANTHROPIC_API_KEY from the environment

    summary, decisions, spent = run_agent(client)

    print(f"\n{summary}\n")
    for name, d in decisions.items():
        print(f"  {name:<16}{d['disposition']:<12}{d['reason']}")

    agreed, coverage, lines = evaluate(decisions)
    gate = "PASS" if coverage == 1.0 and agreed >= 0.8 * len(APPS) else "FAIL"
    print(f"\nEVAL  {gate}: {agreed} of {len(APPS)} agree with the architect, "
          f"{coverage:.0%} of apps decided, ${spent:.4f} spent")
    print("\n".join(lines))
    print("A difference goes to the architect to discuss: either side may be wrong.")


if __name__ == "__main__":
    main()
