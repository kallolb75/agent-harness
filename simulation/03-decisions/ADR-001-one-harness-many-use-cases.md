# ADR-001: One harness, one use case per modernization phase

Status: accepted. Date: week 1 of the simulated POC. Requirements: REQ-001 to REQ-009.

## Context

The client asked for three things in three weeks: a disposition per application, the
ORDPRICE rules with parity tests, and a reconciled CUSTMAST mapping. Each is a different
job, and each needs the same controls: a cost cap, a trail, and a deterministic check
that a person can trust.

## Decision

One harness, three use cases. Each use case is a small agent with its own tools and its
own deterministic eval. The controls are shared: the tool-use loop, the turn cap, the
budget checked before every model call, the priced ledger, and the rule that the model
proposes while code decides.

| Phase | Use case | Deterministic check |
| --- | --- | --- |
| Assess | Portfolio triage | Agreement with the architect's call, per application |
| Understand | Legacy intake | Rule recall, valid line citations, test values re-computed by the legacy oracle |
| Migrate data | Data mapping | Reconciliation to the legacy control totals |

## Consequences

- A new use case is a tools list, a system prompt and an eval. The controls come with it.
- All three use cases write spans through the shared tracer (`harness/telemetry.py`):
  a run, each turn, each model call with tokens and cost, each tool call with its result.
  Any run reads back as a tree with `python -m harness.telemetry runs/<run_id>` (REQ-009).
- Still separate: triage and mapping keep their own small loop instead of the root
  harness's `LLM` class and orchestrator. Extracting one shared core is on the roadmap.
