# Use case: portfolio triage (Assess)

The smallest complete agent harness in this repo, and the Assess phase of a modernization program. One file, one agent, three tools,
about 190 lines with comments. Read it in ten minutes, explain it in two.

**The job.** An architect hands over an application inventory. The agent reads each
application and recommends what to do with it: retain, retire, rehost, replatform,
repurchase or refactor, with a one-sentence reason a CIO would accept. This is the
first step of almost every modernization assessment, done by an agent with guardrails.

```bash
uv run python -m usecases.portfolio_triage.triage --fake    # offline: scripted replies, no key, no cost
uv run pytest usecases                                      # 5 tests, offline
uv run python -m usecases.portfolio_triage.triage           # real run: needs ANTHROPIC_API_KEY, a few cents
```

## The files

| File | What it is |
| --- | --- |
| `triage.py` | The whole harness, in five numbered parts |
| `apps.json` | Five made-up applications, each with the disposition a human architect chose (`expected`) |
| `fake.py` | A stand-in client that replays five scripted replies, so it runs without a key |
| `test_triage.py` | Five tests: a full run, the guardrails, and that the answer key stays hidden |

## The five parts of `triage.py`

| Part | What it is | Where |
| --- | --- | --- |
| 1. The loop | Call the model. If it asked for tools, run them and send the results back. Repeat until it stops asking | `run_agent()` |
| 2. Tools | `list_apps`, `get_app`, `record_decision`: a name, a description and a JSON Schema each | `TOOLS`, `run_tool()` |
| 3. Guardrails | A turn cap, a budget checked before every call, a cut-off reply treated as a failure, and every tool input checked in code | `run_agent()`, `run_tool()` |
| 4. Telemetry | One line per model call (tokens, cost, stop reason) and per tool call (input, result, errors) | the `print` lines in `run_agent()` |
| 5. The eval | The agent's decisions compared with the architect's; PASS needs every app decided and at least 4 of 5 in agreement | `evaluate()` |

## What the fake run shows

Run it with `--fake` and watch three things:

1. **Parallel tool requests.** On turn 2 the model asks for five `get_app` calls in one
   reply. The harness runs all five and sends the five results back in one message,
   each tagged with the id of the request it answers.
2. **A guardrail catching a mistake.** On turn 3 the model records HR-REPORTS as
   `decommission`, which is not an allowed disposition. `run_tool()` refuses it and
   returns an error result.
3. **The model correcting itself.** On turn 4 it reads the error and records `retire`.

## Say it in 60 seconds

> It's a portfolio triage agent: the first step of a modernization assessment. One
> agent with three tools: list the applications, read one, record a decision. The loop
> is the standard one: call the model, run the tools it asks for, send the results
> back with matching ids, stop when it stops asking.
>
> The guardrails are in code, never only in the prompt: a turn cap, a budget checked
> before every call, and every tool input validated, so an invalid disposition is
> refused and the model has to correct itself. Every call is logged with tokens and
> cost. And there's an eval: the agent's calls are compared with an architect's, and
> the answer key is never shown to the agent. A disagreement goes to the architect;
> either side may be wrong.

## How it relates to the legacy intake harness

The legacy intake harness at the root of this repo applies the same ideas to a harder
job, reading legacy code (the Understand phase). It adds:

| Portfolio triage | The legacy intake harness adds |
| --- | --- |
| One agent | An orchestrator that delegates to two worker agents through tools |
| A system prompt in code | Context files per agent, each declaring what it may see |
| `print` lines | A trace of nested spans written to `trace.jsonl`, and a cost ledger |
| Agreement with an architect | A golden set, an oracle, a quality gate and a drift check against a baseline |
| A budget and turn cap | The same, plus caps on how often each worker may run |

## Likely questions

**Why check the disposition in code when the schema already lists the allowed values?**
The schema tells the model what is allowed; it does not stop a bad value reaching
your system. The check in `run_tool()` does. A guardrail you can't test isn't one, and
`test_a_disposition_outside_the_list_is_refused_in_code` tests it.

**Why hide `expected` from the agent?**
It's the answer key. If the agent could read it, the eval would measure copying.

**Why compare with an architect at all?**
Disposition is judgement, so there's no oracle that computes the right answer. A
reviewed human call is the next best reference, and a disagreement is a useful
conversation, not automatically an error.

**What would you add for a real portfolio of 500 applications?**
Data from the CMDB and monitoring instead of a JSON file, batches of applications
with a concurrency cap, a human review queue for low-confidence or high-value
decisions, and the agent's reasons stored next to each decision for audit.

**Why no framework?**
So every step of the loop is visible. A framework wraps the same loop.
