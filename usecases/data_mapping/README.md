# Use case: data mapping and reconciliation (Migrate data)

A one-file agent that maps a legacy customer table to a new schema and proves the
mapping before it may submit it. About 280 lines with comments, the same five parts as
[portfolio triage](../portfolio_triage/README.md).

**The job.** A legacy extract (`CUSTMAST`: zero-padded ids, names as LAST, FIRST,
dates as YYYYMMDD, balances in cents, one-letter status codes) has to land in a new
`customers` table. The agent proposes which source column and which transform fills
each target field. Then it must reconcile: migrate every row and compare the result
with the legacy system's own control totals. Only a mapping that passes may be
submitted for the data owner's sign-off.

```bash
uv run python -m usecases.data_mapping.mapping --fake    # offline: scripted replies, no key, no cost
uv run pytest usecases                                   # the use case tests, offline
uv run python -m usecases.data_mapping.mapping           # real run: needs ANTHROPIC_API_KEY, a few cents
```

## The files

| File | What it is |
| --- | --- |
| `mapping.py` | The whole harness, in five numbered parts |
| `data.json` | Made-up data: the legacy table, the new schema, the legacy control totals, and the data owner's mapping (`golden_mapping`) |
| `fake.py` | A stand-in client that replays seven scripted replies |
| `test_mapping.py` | Eight tests: a full run, reconciliation catching the cents mistake, the guardrails, masking, and the test data itself |

## The tools

| Tool | What it does | Guardrail in code |
| --- | --- | --- |
| `get_source_schema` | Column descriptions, row count, two sample rows | Names and birth dates are masked; the full table is never shown |
| `get_target_schema` | Each target field, its type, whether it is required | |
| `propose_mapping` | Stores a complete mapping: target field, source column, transform | Every target field exactly once; only known columns; only transforms from the fixed list |
| `reconcile` | Migrates every row and runs four checks against the control totals | Runs in code, never in the model |
| `submit_mapping` | Submits the mapping for sign-off | Refused unless the current mapping passed reconciliation |

## How reconciliation works

The legacy system's end-of-day report gives control totals for the same extract. After
migrating every row, the harness checks four things:

| Check | Passes when |
| --- | --- |
| Row count | Same number of rows as the control report (8) |
| Balance total | The migrated balances add up to the control total ($61,187.14) |
| Status counts | 5 active, 2 inactive, 1 closed, as in the control report |
| Required fields | No required field is empty in any row (a failed date conversion would show here) |

This is the oracle for a data migration: the legacy system's own numbers, never the
model's opinion.

## What the fake run shows

1. **A plausible mistake.** The model maps `balance` with `copy`, missing that `BAL_AMT`
   is in cents.
2. **Reconciliation catching it.** The balance total comes out at 6,118,714 against a
   control total of 61,187.14: one hundred times too large. In the same turn the model
   tries to submit, and the harness refuses.
3. **The model fixing it.** It reads the failure, switches to `cents_to_dollars`,
   reconciles again, passes, and submits.

## What it adds to the other use cases

- **The agent checks its own work with a deterministic tool** and must loop until it
  passes. Portfolio triage has no such check; legacy intake checks only after the run.
- **The agent never writes code.** It chooses transforms by name from a list of small,
  tested functions, so nothing the model writes ever runs on the data. A proposal
  containing code is refused (`test_a_transform_outside_the_list_is_refused`).
- **Data minimization.** The agent sees descriptions and two masked rows. In a regulated
  client, personal data in prompts is the first question security asks.

## Say it in 60 seconds

> It's the data migration step of a modernization. The agent reads the legacy and
> target schemas, sees only two masked sample rows, and proposes a mapping using a fixed
> list of tested transforms, so it never writes code that touches the data. Then it has
> to prove the mapping: the harness migrates every row and reconciles against the legacy
> system's own control totals: row count, balance total, status counts, required fields.
> Submitting before reconciliation passes is refused in code. In the demo the model
> leaves balances in cents, reconciliation shows a total one hundred times too large,
> and the model fixes it. Every call is logged with tokens and cost, and the final
> mapping is graded against the one the data owner signed off.

## Likely questions

**Why not let the model write the transformation code?**
Code the model writes would run on customer data without review. A fixed list of
tested transforms keeps every operation known and reviewable. A new transform is added
by a person, with a test, once.

**What if the control totals pass but a field is still wrong?**
They can: swap first and last names and every total still matches. That is why the
mapping is also graded against the data owner's, and why a real migration adds field
level checks on a sample, such as hashes of key fields compared row by row.

**How does this scale to hundreds of tables?**
One agent run per table, in parallel with a cap, ordered by the dependency graph
between tables. Control totals per table from the legacy reports. The data owner signs
off per table, and the mapping plus its reconciliation report become the audit record.
