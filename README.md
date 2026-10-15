# AgentHarness

A small, readable agent harness for AI-assisted modernization.

The harness gives every agent the same loop, guardrails, cost control, tracing and
evaluation. Each phase of a modernization program plugs in as a use case:

| Phase | Use case | What the agent does | How it is graded | Where |
| --- | --- | --- | --- | --- |
| Assess | **Portfolio triage** | Recommends retain, retire, rehost, replatform, repurchase or refactor for each application, with a reason | Agreement with an architect's calls, which the agent never sees | [usecases/portfolio_triage/](usecases/portfolio_triage/README.md) |
| Understand | **Legacy intake** | An orchestrator directs two workers over a COBOL program: one extracts the business rules, one writes parity tests | Rules found by a person, and an oracle that computes what the COBOL really returns | This folder (below) |
| Migrate data | **Data mapping** | Maps a legacy table to a new schema and must prove it by reconciliation before it may submit | Reconciliation against the legacy control totals, and the data owner's mapping | [usecases/data_mapping/](usecases/data_mapping/README.md) |

New to agent harnesses? Start with portfolio triage: one file, one agent, three tools.
Legacy intake is the fuller design.

## See all three in one engagement

[simulation/](simulation/README.md) runs a simulated client engagement for a fictional
food distributor, Lone Star Foodservice: meeting transcript, numbered requirements, design
diagrams, decision records, all three use cases in one command, and a report that traces
every requirement to evidence. [infra/](infra/README.md) deploys the harness as a Cloud
Run job with Terraform.

```bash
uv run python -m simulation.run_engagement        # fake mode, no API key
```

## Legacy intake (Understand)

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

New here? Start with [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md): setup, a first run, and how to read what it prints.

Want the smallest version first? [usecases/portfolio_triage/](usecases/portfolio_triage/README.md) is a one-file agent: the same loop, tools, guardrails, telemetry and eval in about 190 lines.

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
| `usecases/` | The other use cases, one folder each: portfolio triage and data mapping |
| `runs/` | One folder per run: `result.json`, `tokens.jsonl`, `trace.jsonl` (not committed) |

## Roadmap

Today the legacy intake harness lives at the root and each other use case is a
self-contained folder under `usecases/`. The next step is to pull the shared parts
(the loop, the one door to the model, the guardrails, the trace and the eval runner)
into a `core/` package, and move legacy intake to `usecases/legacy_intake/`. A new use
case would then be only its agent instructions, its tools, its data and its answer key.

## What it is not

A teaching-sized harness: one program, run in sequence, state in memory, files on
disk. [WALKTHROUGH.md](WALKTHROUGH.md) section 7 lists what a production version would
add.

## License

MIT. See [LICENSE](LICENSE).
