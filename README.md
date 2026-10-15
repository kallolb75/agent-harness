# AgentHarness

A small, readable agent harness for legacy code intake.

An orchestrator model directs two worker agents over one COBOL program. The
**Analyzer** extracts the program's business rules, each with the source lines that
prove it. The **Test-writer** turns those rules into parity tests: cases a modern
rewrite must pass to show it behaves exactly like the original.

Around the agents sit four controls and a trace:

- **Context:** each agent sees only the inputs its file declares
- **Order:** out-of-order steps are refused in code
- **Cost:** every model call is priced and logged, and a budget cap is checked before each call
- **Drift:** every run is scored against a fixed quality bar and against a reviewed baseline
- **Telemetry:** every step of a run is a span in a trace you can read as a tree

It is built to be read: about 1,100 lines of Python, much of it comments, using only
the Anthropic SDK and the standard library. No agent framework, so every moving part
is visible. The COBOL
program, its history and its pricing memo are invented for the example.

## What one run does

```
run.py ──> orchestrator (Sonnet) ──tool──> analyzer (Sonnet) ──┐
              │    ^                                         ├──> STATE (blackboard)
              │    └──one-line summaries─────────────────────┘        │
              └──tool──> test_writer (Haiku) <── reads analysis ──────┘

every model call ──> llm.py: budget check, call, price, log, trace
end of run      ──> evals/check.py: quality gate + drift check against the baseline
```

## Quick start

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                                # creates .venv, installs anthropic and pytest
uv run run.py legacy/ORDPRICE.cbl --fake               # offline: scripted replies, no key, no cost
uv run run.py legacy/ORDPRICE.cbl --fake --trace       # same, printing every step as it happens
uv run pytest                                          # the test suite, offline
```

A real run needs an Anthropic API key in your environment:

```bash
export ANTHROPIC_API_KEY=...                           # never commit it
uv run run.py legacy/ORDPRICE.cbl                      # real run; the cost table prints at the end
uv run run.py legacy/ORDPRICE.cbl --budget 0.01        # watch the budget cap stop a run
```

After a run:

```bash
uv run python -m harness.telemetry runs/<run_id>                        # the run as a tree of spans
uv run python -m evals.check runs/<run_id>/result.json                  # re-score a run
uv run python -m evals.check runs/<run_id>/result.json --set-baseline   # accept a reviewed run as the baseline
```

## Read in this order

1. [docs/CALL_FLOW.md](docs/CALL_FLOW.md): who calls whom, and exactly what each model call sees
2. [WALKTHROUGH.md](WALKTHROUGH.md): the design choices, the four controls, a file-by-file reading guide
3. [docs/TELEMETRY.md](docs/TELEMETRY.md): the cost ledger, the trace, and how to read them
4. [docs/EVALS.md](docs/EVALS.md): the quality gate, the drift check, the golden set and the oracle
5. [DRILL.md](DRILL.md): rebuild the loop from a blank file, then break each control on purpose

## What's where

| Path | What it is |
| --- | --- |
| `run.py` | Entry point: prepare, run the intake, record, evaluate, print |
| `harness/orchestrator.py` | The tool-use loop. Workers are tools. Enforces order and the turn cap |
| `harness/agents.py` | A worker: one call, JSON back, one retry on bad JSON |
| `harness/llm.py` | The one door to the model: budget check, call, price, log, trace. Fake mode lives here |
| `harness/context.py` | Builds each agent's context from `AGENTS.md`, its own file and its declared inputs |
| `harness/telemetry.py` | The tracer, and the tree view of a finished trace |
| `harness/config.py` | Prices, budget, turn cap, agent names |
| `AGENTS.md` | Shared rules every agent reads |
| `agents/*.md` | One context file per agent: model, token cap and inputs in the header; instructions below |
| `legacy/ORDPRICE.cbl` | The legacy program: 74 lines, 5 paragraphs, 9 business rules |
| `evals/check.py` | The quality gate and the drift check |
| `evals/golden.json` | The rules a person found in the code |
| `evals/oracle.py` | What the COBOL really returns, checked against the compiled program on 3,000 cases |
| `evals/baseline.json` | The reviewed run later runs are compared with |
| `tests/` | Proof the controls work: each test breaks something and expects the harness to notice |
| `fake/` | Scripted model replies for offline runs and tests |
| `drill/answer_key.py` | The smallest complete harness loop, for the drill |
| `runs/` | One folder per run: `result.json`, `tokens.jsonl`, `trace.jsonl` (not committed) |

## What it is not

A teaching-sized harness: one program, run in sequence, state in memory, files on
disk. [WALKTHROUGH.md](WALKTHROUGH.md) section 7 lists what a production version would
add.

## License

MIT. See [LICENSE](LICENSE).
