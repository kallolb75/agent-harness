# Telemetry: what happened, what it cost, how long it took

Every run writes three files to `runs/<run_id>/`. Each one answers a different question.

| File | Question it answers | Written by | One line per |
| --- | --- | --- | --- |
| `tokens.jsonl` | What did each model call cost? | `harness/llm.py`, `LLM._log()` | model call |
| `trace.jsonl` | What happened, in what order, and how long did each step take? | `harness/telemetry.py`, `Tracer` | step (span) |
| `result.json` | What did the agents produce, and how good was it? | `run.py`, then scored by `evals/check.py` | run |

Telemetry is about the run as it ran. Evals (see [EVALS.md](EVALS.md)) are about the
quality of what it produced. Drift is evals compared over time.

## Traces and spans

A **span** is one unit of work: a name, when it started, how long it took, whether it
succeeded, and attributes describing it. A **trace** is all the spans of one run,
linked into a tree by each span's `parent_id`.

```
run 20261015-150231-fake  ORDPRICE.cbl  [18.1 ms]
├─ orchestrator.turn 1  [5.1 ms]
│  ├─ llm.call  orchestrator  claude-sonnet-5-5  912 in / 48 out  $0.0023  stop=tool_use  [1.3 ms]
│  └─ tool.call run_analyzer  ->  Analysis stored: 9 rules (R1, R2, ...  [2.3 ms]
│     └─ worker analyzer  [1.7 ms]
│        └─ worker.attempt 1  [1.3 ms]
│           └─ llm.call  analyzer  claude-sonnet-5-5  1688 in / 842 out  $0.0118  stop=end_turn  [0.7 ms]
├─ orchestrator.turn 2  [3.9 ms]
│  ├─ llm.call  orchestrator  claude-sonnet-5-5  1104 in / 61 out  $0.0028  stop=tool_use  [0.6 ms]
│  └─ tool.call run_test_writer  ->  Tests stored: 10 cases.  [2.4 ms]
│     └─ worker test_writer  [1.7 ms]
│        └─ worker.attempt 1  [1.4 ms]
│           └─ llm.call  test_writer  claude-haiku-5-5  2804 in / 1376 out  $0.0010  stop=end_turn  [0.7 ms]
├─ orchestrator.turn 3  [1.7 ms]
│  └─ llm.call  orchestrator  claude-sonnet-5-5  1190 in / 72 out  $0.0031  stop=end_turn  [0.9 ms]
└─ eval  drift=OK  gate=PASS  [0.6 ms]
```

This is a `--fake` run, so the durations are milliseconds and the token counts are
scripted. On a real run each `llm.call` takes seconds and the counts are the API's.

Print it for any run:

```bash
uv run python -m harness.telemetry runs/<run_id>
```

Or watch it live, each step printed as it starts (▶) and ends (✓, or ✗ on error):

```bash
uv run run.py legacy/ORDPRICE.cbl --fake --trace
```

## The spans this harness records

| Span | Opened in | Attributes at start | Attributes added when it ends |
| --- | --- | --- | --- |
| `run` | `run.py` | source, fake, budget_usd | spent_usd, verdict, gate |
| `orchestrator.turn` | `run_orchestrator` | turn | |
| `llm.call` | `LLM.call` | agent, model, max_tokens, turn_messages | input_tokens, output_tokens, cache_read, cache_write, cost_usd, run_total_usd, stop_reason |
| `tool.call` | `run_orchestrator` | tool, tool_use_id, input | result (the text the orchestrator gets back), refused |
| `worker` | `run_worker` | agent, inputs | attempts |
| `worker.attempt` | `run_worker` | agent, attempt | valid, and problem when invalid |
| `eval` | `run.py` | | verdict, gate, metrics |

Every span also has `trace_id` (the run id), `span_id`, `parent_id`, `status`
(`ok` or `error`), `started_at` and `duration_ms`. When a step raises, its span and
every span above it are marked `error` with the message, so the tree shows the path
the failure took. Telemetry records failures; it never swallows them.

## Questions you can answer from these files

| Question | Where to look |
| --- | --- |
| Which agent costs the most? | The cost table printed at the end of the run, or sum `cost_usd` per agent in `tokens.jsonl` |
| Why is the orchestrator getting more expensive each turn? | `turn_messages` and `input_tokens` on its `llm.call` spans: the whole conversation is resent every turn |
| Did a worker need a retry? | A `worker` span with `attempts=2`, and a `worker.attempt` marked invalid with its problem |
| Why did the run stop? | The span marked `error` deepest in the tree: a budget stop shows on an `llm.call` with no token counts |
| Did the orchestrator try something out of order? | A `tool.call` with `refused=true` |
| Where does the time go? | `duration_ms` on `llm.call` against the parent spans: on a real run, nearly all of it is model latency |

## How this maps to OpenTelemetry

The structure is the same as OpenTelemetry's: trace id, span id, parent id, status,
attributes. It is written with the standard library so the harness has one
dependency. To export to a real backend (Cloud Trace, Jaeger, Honeycomb), replace the
`Tracer` class with the OpenTelemetry SDK. The call sites, `with tracer.span(...)`,
stay the same. The attributes would take OpenTelemetry's generative AI names:

| Here | OpenTelemetry generative AI convention |
| --- | --- |
| `model` | `gen_ai.request.model` |
| `input_tokens` | `gen_ai.usage.input_tokens` |
| `output_tokens` | `gen_ai.usage.output_tokens` |
| `stop_reason` | `gen_ai.response.finish_reasons` |
| `tool` on `tool.call` | `gen_ai.tool.name` |

## Limits

- **One thread.** The current parent is the last open span on a list. Parallel workers
  would need the parent carried per task (Python's `contextvars`), which is what the
  OpenTelemetry SDK does.
- **Content in traces.** `tool.call` records the tool's input and result. On real
  client code, mask anything sensitive before it lands in a trace, or record sizes
  and hashes instead of content.
- **No export, no sampling.** Files on disk, every span kept. Fine for one program;
  a large estate would export to a backend and sample.
