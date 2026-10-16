# Getting started with AgentHarness

## What it is, in one paragraph

AgentHarness is a small Python program that uses AI agents to study an old COBOL
program. One agent, the **orchestrator**, is in charge. It hands work to two helpers:
the **Analyzer** reads the COBOL and writes down its business rules, each with the
line numbers that prove it, and the **Test-writer** turns those rules into tests a
modern rewrite would have to pass. Around the agents, the harness adds safety rails:
it caps spending, enforces the order of steps, records everything that happens, and
grades every run.

You can run it without an API key and for free. It replays recorded answers instead
of calling the model, so that's where to start.

## What you need

| Thing | Why | Check |
| --- | --- | --- |
| A Mac or Linux terminal | To run commands | Open Terminal |
| [uv](https://docs.astral.sh/uv/) | Installs Python 3.12 and the project's libraries for you | `uv --version` |
| git | To get the code | `git --version` |
| An Anthropic API key | Only for real runs, later | Not needed today |

If `uv` is missing, install it with `brew install uv` (or see its website). You don't
need to install Python yourself; uv fetches the right version.

## Step 1. Get the code and set it up (5 minutes)

```bash
git clone https://github.com/kallolb75/agent-harness.git
cd agent-harness
uv sync
```

`uv sync` creates a private Python environment in a folder called `.venv` and installs
the two libraries the project needs: the Anthropic SDK and pytest. Nothing is
installed system-wide.

## Step 2. Prove it works (1 minute)

```bash
uv run pytest
```

You should see `23 passed`. Each test breaks something on purpose, for example
overspending or calling steps out of order, and checks that the harness catches it.
Green means the safety rails work.

## Step 3. Your first run, offline and free (2 minutes)

```bash
uv run run.py legacy/ORDPRICE.cbl --fake --trace
```

- `legacy/ORDPRICE.cbl` is the COBOL program being studied. It prices one order line
  in 74 lines.
- `--fake` replays scripted model replies from the `fake/` folder: no key, no cost.
- `--trace` prints every step as it happens.

## Step 4. Read what it printed

The output comes in five parts, top to bottom:

1. **The live trace.** Lines starting with ▶ mean a step started; ✓ means it
   finished. Watch the order: the orchestrator calls the Analyzer, then the
   Test-writer, then finishes.
2. **The summary.** The orchestrator's final words: 9 rules found, 10 tests written,
   and one question for a human expert.
3. **The cost table.** Calls, tokens and dollars per agent. In fake mode the numbers
   are scripted, so ignore the dollars.
4. **The eval report.** Two verdicts:
   - **Quality gate PASS/FAIL**: was this run good enough?
   - **Drift check OK/DRIFT**: is it worse than the last good run?

   You'll see a WARNING that the baseline is a fake run. That's expected on a fresh
   copy.
5. **The trace tree.** The same run drawn as a tree. Five model calls in all: three
   for the orchestrator, one for each helper.

Everything is saved to a new folder, `runs/<date-time>-fake/`:

| File | Holds |
| --- | --- |
| `tokens.jsonl` | One line per model call, with its cost |
| `trace.jsonl` | One line per step, with timing |
| `result.json` | The rules and tests the agents produced |

## Step 5. The one idea that makes the code readable

There are **two kinds of conversation** running at once:

- **The orchestrator's conversation is long and grows.** Every turn it resends
  everything so far, because the model remembers nothing between calls. It never
  sees the COBOL. It only gets one-line summaries like "Analysis stored: 9 rules".
- **Each helper gets a short, fresh conversation.** It sees the shared rules, its own
  instructions and only the inputs it needs, then it's thrown away.

The helpers' full results go into a shared dictionary called `state`. That's how the
Test-writer reads the Analyzer's actual rules instead of the orchestrator's summary
of them.

If the code ever confuses you, come back to this paragraph. Then open
[CALL_FLOW.md](CALL_FLOW.md), which draws it.

## Step 6. Where things live

Read in this order:

| Order | File | In plain words |
| --- | --- | --- |
| 1 | `run.py` | The start button. Four numbered steps: prepare, run, record, grade |
| 2 | `harness/orchestrator.py` | The loop: ask the model, run the tool it asked for, send back the result, repeat |
| 3 | `harness/agents.py` | One helper: one model call, a JSON answer back, one retry if the JSON is bad |
| 4 | `harness/llm.py` | The only door to the model. Checks the budget, makes the call, prices it, logs it |
| 5 | `harness/context.py` | Decides what each agent gets to see |
| 6 | `agents/*.md` | Each agent's instructions, in plain English. Edit these to change behaviour |
| 7 | `harness/telemetry.py` | Records each step and draws the tree |
| 8 | `evals/check.py` | Grades the run against answers a person wrote and the program's real outputs |

Each Python function starts with a short note saying who calls it and what it calls.

## Step 7. A real run (when you're ready, a few cents)

```bash
export ANTHROPIC_API_KEY=your-key-here     # this terminal only; never put it in a file
uv run run.py legacy/ORDPRICE.cbl
```

Same output, but now the model really answers. Note three things: the run total in
the cost table, which agent cost the most, and both verdicts. If you'd stand behind
the run, make it the reference future runs are compared with:

```bash
uv run python -m evals.check runs/<run_id>/result.json --set-baseline
```

## When something goes wrong

| You see | It means | Do this |
| --- | --- | --- |
| `uv: command not found` | uv isn't installed | `brew install uv` |
| An authentication error on a real run | No API key in this terminal | `export ANTHROPIC_API_KEY=...` again |
| `STOPPED: ... stopping before the call` | The budget cap worked | Add `--budget 1.00` |
| `FAILED: ... cut off at max_tokens` | A reply hit its length limit | Raise `max_tokens` in the agent file the message names |
| `WARNING: the baseline ... is a fake run` | Normal on a fresh copy | Set a reviewed real run as the baseline |
| Your editor shows red imports | It's using the wrong Python | Point it at `.venv/bin/python` in the project folder |

## Next

1. Read [CALL_FLOW.md](CALL_FLOW.md), then [WALKTHROUGH.md](../WALKTHROUGH.md).
2. Break each safety rail on purpose and watch the tests catch it: comment out the
   budget check in `harness/llm.py`, or the order check in `harness/orchestrator.py`,
   then run `uv run pytest`.
3. Read [TELEMETRY.md](TELEMETRY.md) and [EVALS.md](EVALS.md) when you want the depth
   on tracing and grading.
