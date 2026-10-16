# Evals and drift: how good is a run, and is it getting worse?

## The words

| Term | Meaning here |
| --- | --- |
| **Eval** | A check that scores what the agents produced. Here: four metrics in `evals/check.py` |
| **Golden set** | The answers a person wrote by hand, to score the model against. `evals/golden.json`: the eight business rules a person found in `ORDPRICE.cbl` |
| **Oracle** | Whatever tells you the correct output for an input. In a modernization it is the legacy system itself. `evals/oracle.py` stands in for running the COBOL |
| **Baseline** | A reviewed, good run that later runs are compared with. `evals/baseline.json` |
| **Fingerprint** | A hash of each context file and the model per agent, saved with every run, so you can tell what changed between two runs |
| **Quality gate** | A fixed floor each metric must reach for the run to be usable |
| **Drift** | The same job getting worse over time without anyone noticing |

## Two questions, kept apart

| | Quality gate | Drift check |
| --- | --- | --- |
| **Asks** | Is this run good enough to use? | Is this run worse than the last good one? |
| **Compared with** | Fixed floors (`GATE` in `evals/check.py`) | The baseline run's scores |
| **Fails when** | A metric is below its floor | A metric fell more than `TOLERANCE` (0.10) below the baseline |
| **Catches** | A bad run, even on the first day | A run that got worse, even if it is still above the floor |
| **Misses on its own** | Slow decline while staying above the floor | A run that was always bad, if the baseline was bad too |

That last row is why there are two checks. Each covers the other's blind spot.

## The four metrics

| Metric | Question | How it is computed | Floor | Catches |
| --- | --- | --- | --- | --- |
| `rule_recall` | Did the Analyzer find every rule a person found? | Share of golden rules matched by some extracted rule. A golden rule matches when the rule's text holds every keyword group in `golden.json` | 0.875 (at most one miss) | A prompt edit that makes the Analyzer drop a rule, such as the fee being taxed |
| `citations_valid` | Are the cited source lines real? | Share of rules whose every cited line number exists in the file | 1.0 | Invented evidence: a citation to line 412 of a 74-line file |
| `test_accuracy` | Are the generated tests right? | Share of tests whose expected output equals what the oracle computes for the same inputs | 0.9 | Plausible arithmetic that is a cent off; a cheaper model getting the order of discounts wrong |
| `enough_tests` | Did enough tests come back? | 1 if at least 8 tests, else 0 | 1.0 | A truncated or lazy reply |

## The oracle is the key idea

A test's expected value written by a model is a **claim**. It might be wrong in
exactly the way the analysis was wrong, so the model cannot check itself. The
expected value has to come from somewhere independent: the legacy system.

In a real program you run the COBOL with the test inputs and record what it returns
(a golden master). Here `evals/oracle.py` follows `ORDPRICE.cbl` paragraph by
paragraph in Python with `Decimal` arithmetic. `evals/verify_oracle.py` checks it
against the program compiled with GnuCOBOL: 3,000 random orders, zero mismatches.
Run it yourself with `uv run python -m evals.verify_oracle` once `cobc` is installed.

So the Test-writer's job is to choose good **inputs** (boundaries, each customer type,
each rule). Whether its **expected outputs** are right is decided by the oracle.

## Random inputs miss threshold defects

`evals/translation_parity.py` makes the point with numbers. It seeds six defects a fluent
but careless translation of ORDPRICE makes, then compares each variant with the compiled
COBOL on two input sets: 3,000 random orders, and 96 orders built at every threshold the
rules contain.

| Defect | Random fails | Boundary fails |
| --- | --- | --- |
| Float instead of decimal | 86 | 29 |
| Discounts added, not compounded | 802 | 9 |
| Fee added after tax | 27 | 7 |
| Half-even rounding | 79 | 25 |
| Credit hold at `>=` the limit | 0 | 15 |
| Fee at `<=` 25.00 | 0 | 2 |

The random set misses two defects entirely; the boundary set catches all six. Run it with
`uv run python -m evals.translation_parity` once `cobc` is installed.

## What changed, and where to look

Every run saves its fingerprints. The report lists what differs from the baseline:

| The report says | Most likely cause | Look at |
| --- | --- | --- |
| `prompt file agents/analyzer.md` | Someone edited that file | The diff of that file |
| `model for test_writer: claude-haiku-5-5 -> claude-sonnet-5-5` | A model choice changed | Cost against accuracy for the two models |
| `nothing: same prompts, same models` | Nothing changed on your side | The provider's model behind the same name, or the input changed shape. Pin model versions |

## Reading a report

```
QUALITY GATE  PASS    (fixed floors in evals/check.py GATE)
DRIFT CHECK   OK    (against baseline run 20261009-183651-fake)
  metric           this run   floor  baseline
  rule_recall           1.0   0.875       1.0
  citations_valid       1.0     1.0       1.0
  test_accuracy         1.0     0.9       1.0
  enough_tests          1.0     1.0       1.0
  changed since baseline: nothing: same prompts, same models (so look at the provider's model or the input)
  WARNING: the baseline (20261009-183651-fake) is a fake run; it says nothing about the real model. Review a real run and set it as the baseline
```

Below the table the report lists every missed rule, invalid citation and wrong test
by name, so a failure points straight at the evidence.

## The lifecycle

1. **Run** the harness. Every run is scored automatically at the end.
2. **Review** a run by hand: read the rules against the source, spot-check the tests.
3. **Set it as the baseline** once you would stand behind it:
   `uv run python -m evals.check runs/<run_id>/result.json --set-baseline`.
   The command refuses a run that fails the gate, and a fake run unless you add
   `--allow-fake`, because a fake run's scores say nothing about the real model.
4. **Gate every change.** Any edit to `AGENTS.md` or `agents/*.md`, or a model change,
   gets a run and must pass the gate without drift before it is kept.
5. **Run on a schedule** with nothing changed. If scores fall and the report says
   nothing changed on your side, the model or the input moved.

## Why deterministic checks, and not a model as judge

The same output always gets the same score, so a change in score means the output
changed. A model grading a model can drift too, and then you cannot tell which one
moved. A model as judge is useful for qualities keywords cannot see, such as whether
a rule's description is clear to a business analyst. It then needs calibrating
against human labels, and its own drift check.

## The checker is tested too

A check that has never been seen to fail proves nothing. `tests/test_eval.py` takes a
known-good run, breaks it the way real drift shows up, and asserts the checker
notices: a dropped rule, a wrong expected value, two wrong tests, an invented line
number, a changed prompt file, a changed model, a run below the floor that the drift
check alone would pass, a fake baseline, and an attempt to set a bad baseline.
Remove the gate or the drift comparison from `evaluate()` and tests fail.

## Limits

- **Keyword matching** can pass a rule that only names the words, or miss one phrased
  with synonyms. A structured rule category per extracted rule would fix that.
- **A small golden set.** Eight rules for one program. At scale, subject matter
  experts label a sample of programs per business domain.
- **A hand-written oracle.** It was checked against the compiled COBOL, but on a real
  estate the oracle is the legacy system run on captured production inputs.
- **Correct tests can still miss behaviour.** Every test can agree with the oracle and
  the suite can still skip a paragraph. Measuring which COBOL paragraphs the tests
  reach would close that gap.
