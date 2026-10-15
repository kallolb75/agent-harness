# Walkthrough

How this harness works, why each choice was made, and where each one lives in the
code. Read it next to the code; every claim here points at a file. For who calls
whom, start with [docs/CALL_FLOW.md](docs/CALL_FLOW.md).

## 1. The problem

Legacy code that nobody fully understands. Before you modernize a COBOL program, you
need two things: its business rules written down, and a set of parity tests the
rewrite must pass to prove it behaves the same.

This harness does that intake for one program. An orchestrator agent directs two
workers through tools. The Analyzer reads the COBOL and returns each business rule
with the line numbers that prove it. The Test-writer turns those rules into parity
tests, with a case on each side of every threshold.

## 2. The map

```
run.py ──> orchestrator (Sonnet) ──tool──> analyzer (Sonnet) ──┐
              │    ^                                         ├──> STATE (blackboard)
              │    └──one-line summaries─────────────────────┘        │
              └──tool──> test_writer (Haiku) <── reads analysis ──────┘
                                    │
every call ──> llm.py: budget check, call, price, log, trace ──> runs/<id>/tokens.jsonl, trace.jsonl
end of run ──> evals/check.py: golden rules + oracle + gate + baseline ──> PASS/FAIL, OK/DRIFT
```

## 3. The four controls, and the trace

### Order · `harness/orchestrator.py`

- **Workers are tools.** The orchestrator model sees `run_analyzer` and
  `run_test_writer` as tools with descriptions. It decides what to call; the harness
  runs it.
- **Full outputs go to state, summaries go to the orchestrator.** The Analyzer's nine
  rules land in `state["analysis"]`. The orchestrator gets "Analysis stored: 9 rules".
  Its context stays small, and the Test-writer reads the Analyzer's actual output
  rather than the orchestrator's retelling of it.
- **Rules live in code.** Test-writer before Analyzer is refused, and so is a third
  Analyzer run. The prompt states both rules as well, but a prompt is a request.
- **The judgement it does make:** whether an open question is about unclear code
  (re-run the Analyzer with a focus) or about business policy (send it to a person).
- **The trade-off:** for a fixed two-step job, a plain pipeline in code would be
  cheaper and more predictable. A model as orchestrator earns its place only where the
  next step depends on judgement. In production, use fixed workflows where the steps
  are known and put a model only at the decision points.

### Context · `harness/context.py`, `AGENTS.md`, `agents/*.md`

- **Three layers:** shared rules (`AGENTS.md`), the agent's own file, then its declared
  inputs. The same idea as an AGENTS.md or CLAUDE.md in a code repository.
- **Declared in the file.** `inputs: analysis, source` in the agent's header decides
  what it sees. Change the context by editing a file, with no Python change.
- **Isolation.** A worker never sees the orchestrator's conversation. Each call starts
  fresh with only what it needs.
- **Shared vocabulary.** `AGENTS.md` fixes the field names (`cust_type`, `total`,
  `status`) so one agent's output fits the next agent's input and the eval's oracle.
- **Evidence.** The source goes in with line numbers, every rule must cite lines, and
  the eval rejects a citation past the end of the file.
- **Caching.** The stable prefix (shared rules plus instructions) is marked for prompt
  caching. Below the model's minimum cacheable length it is skipped, which is the case
  for this small program; on a real codebase the shared context is large and caching
  pays.

### Cost · `harness/llm.py`, `harness/config.py`

- **One door.** Every call goes through `LLM.call()`, so nothing escapes the ledger,
  the cap or the trace.
- **Budget checked before the call.** The worst overshoot is one call, and that call's
  output is bounded by the agent's `max_tokens`.
- **Model per agent.** Sonnet reads code; Haiku writes tests at a twentieth of the
  input price. The eval tells you whether the cheap model is good enough.
- **Smaller contexts.** Workers see declared inputs only; the orchestrator sees summaries.
- **A ledger.** `tokens.jsonl` has one priced line per call, so you can find the
  expensive agent in a minute.
- **Bounded retries and turns.** One retry on bad JSON, six orchestrator turns, two
  Analyzer runs.

### Drift · `evals/check.py`, `evals/golden.json`, `evals/oracle.py`

Full detail in [docs/EVALS.md](docs/EVALS.md).

- **Two checks.** A quality gate (is this run good enough, against fixed floors) and a
  drift check (is it worse than the reviewed baseline). Each covers the other's blind
  spot.
- **Four metrics.** Rule recall against eight rules a person found in the code;
  citation validity; test accuracy, where every expected value the Test-writer claims
  is recomputed by the oracle; and enough tests.
- **The oracle is the key idea.** An expected value written by a model is a claim. In a
  real program the oracle is the legacy system: run the COBOL with the test inputs and
  record what it returns. Here `oracle.py` stands in, checked against the compiled
  COBOL on 3,000 random cases with zero mismatches.
- **Fingerprints.** Each run records a hash of every context file and the model per
  agent. The report names what changed since the baseline, so you know where to look.
- **Deterministic on purpose.** Keywords and arithmetic, no model grading a model.

### Telemetry · `harness/telemetry.py`

Full detail in [docs/TELEMETRY.md](docs/TELEMETRY.md).

- **A trace per run.** Every step is a span: the run, each orchestrator turn, each
  model call, each tool call, each worker and each worker attempt. Spans nest the way
  the calls nest.
- **Failures are recorded.** A step that raises marks its span, and every span above
  it, as an error with the message.
- **Read it as a tree:** `uv run python -m harness.telemetry runs/<run_id>`, or watch it
  live with `--trace`.

## 4. Reading guide, file by file

Read in this order. Java and C# comparisons where they help.

### `harness/llm.py`
- `class BudgetExceeded(Exception)`: a custom exception, like
  `class BudgetExceeded extends RuntimeException {}`. A class body can be just a
  docstring.
- `def __init__(self, ...)`: the constructor. `self` is `this`, written out explicitly
  as the first parameter of every method.
- `import anthropic` inside `__init__`: imported only for real runs, so `--fake` works
  without the SDK or a key.
- `with self.tracer.span("llm.call", ...) as span:`: opens a telemetry span around the
  whole call, so even a call refused by the budget is recorded.
- `request = {...}` then `self.client.messages.create(**request)`: a dict (HashMap), and
  `**` spreads it into named arguments. Same as calling `create(model=..., system=...)`.
- `getattr(usage, "cache_creation_input_tokens", 0) or 0`: read a field that might not
  exist or might be `None`, defaulting to 0.
- `with open(path, "a") as f:`: try-with-resources. The file closes when the block ends.
- `SimpleNamespace(**block)`: turns `{"type": "text"}` into an object with `.type`, so
  fake replies look like real SDK objects.

### `harness/orchestrator.py`
- `TOOLS`: each tool is a name, a description and a JSON Schema for its input. The model
  reads the description as an instruction, so write it like one.
- `for turn in range(1, max_turns + 1):`: `for (int turn = 1; turn <= maxTurns; turn++)`.
- `[to_dict(b) for b in response.content]`: a list comprehension, the same as
  `content.stream().map(this::toDict).collect(toList())`.
- `if response.stop_reason == "max_tokens": raise ...`: a reply cut off mid-sentence is
  not an answer.
- `if response.stop_reason != "tool_use": return ...`: the model is done when it stops
  asking for tools.
- `tool_use_id: block.id`: every result must name the tool request it answers. That
  pairing is how the model matches answers to questions when it asks for several at once.
- `dispatch()` returns a string. Whatever it returns is all the orchestrator learns.

### `harness/agents.py`
- `for attempt in (1, 2):`: loop over a two-item tuple. Two tries, no more.
- `try: ... except ValueError as err:`: `json.loads` raises `JSONDecodeError`, a subclass
  of `ValueError`, so one `except` covers bad JSON and missing keys.
- On failure, the bad reply and the error go back to the model as the next turn.
- `parse_json` takes the outermost `{...}`, which survives a reply wrapped in prose or a
  code fence.

### `harness/context.py`
- `text.split("---", 2)`: split on the first two `---` only, so a `---` in the
  instructions doesn't break parsing. Returns three parts; the first is empty.
- `Path(__file__).resolve().parent.parent`: the project folder, found from this file's
  location, so the code works from any working directory.
- `[ROOT / "AGENTS.md", *sorted(...)]`: `/` joins paths; `*` spreads one list into another.

### `harness/telemetry.py`
- `@contextmanager` with `yield span`: turns a function into something you can use in a
  `with` block. Code before `yield` runs on entry, code in `finally` runs on exit, even
  when the block raises. The closest Java equivalent is try-with-resources around an
  `AutoCloseable`.
- `self._open`: a stack of spans still running. The top one is the parent of the next.

### `evals/check.py`
- `evaluate()` returns a dict, `report()` turns it into text. Keeping scoring and
  printing apart is what lets the tests check scores without parsing text.
- `Decimal`, never `float`, for money. `float` can't hold 0.1 exactly.

### `run.py`
- Four numbered steps: prepare, intake, record, evaluate. `except BudgetExceeded` and
  `except RuntimeError` turn a stopped or failed run into a recorded run, scored on
  whatever it produced.

## 5. Design questions

**Why no agent framework?**
To show the mechanics. Every framework wraps this same loop. Having written it, you can
judge what a framework adds (tracing, parallelism, state persistence) and what it hides.

**Why is the orchestrator a model and not code?**
Because one decision needs judgement: is an open question about unclear code or about
policy? Everything that doesn't need judgement is enforced in code. For a fixed
pipeline, drop the model orchestrator.

**How do agents share information?**
Through state, a shared blackboard. Workers write full outputs there. The orchestrator
gets one-line summaries. Downstream workers read the real thing.

**What happens when a worker returns garbage?**
One retry with the error message, then the run fails and is recorded as failed. A
third attempt rarely fixes what two didn't, and every attempt costs money.

**How do you detect drift? What if the model changes underneath you?**
A golden set, an oracle, a baseline and fingerprints. If scores drop and the
fingerprints say nothing changed on your side, the model or the input moved. Pin
versions and run the eval on a schedule.

**How do you know the generated tests are right?**
You don't trust them. Inputs come from the model; expected outputs come from the
legacy code. Where the model's prediction and the legacy result disagree, either the
analysis is wrong or the legacy does something surprising, and both go to a person.

**Where's the person in the loop?**
Open policy questions go to a subject matter expert. A run becomes the baseline only
after someone reviews it. The golden rules were written by a person from the code.

**What about identity and security?**
Here the tools only call other agents. Against real systems, every tool call runs as
an identity with least privilege and is logged with that identity attached. Whose
identity, the agent's or the user's passed through, is the first design question.
Source code is also untrusted input: a comment can carry instructions, so nothing read
from the code should trigger an action with side effects without a person's approval.

## 6. At the scale of a real estate

Say hundreds of online and batch programs, hundreds of tables and files, millions of
lines. The harness doesn't change. Four things go in front of and around it.

1. **Inventory without a model.** Parse first: the program list, the call graph,
   copybooks, and which program reads and writes which table or file. Deterministic,
   cheap, and it tells you the order to analyze in.
2. **Chunk by program, then paragraph.** One Analyzer run per program, in parallel with
   a concurrency cap. Shared copybooks are analyzed once and cached.
3. **Map, then reduce.** Rules per program roll up into rules per business domain
   (pricing, credit, fulfilment). The domain view is what the business reads.
4. **Eval by sample.** Subject matter experts hand-label a sample of programs per
   domain as the golden set. The oracle is the legacy itself: captured production
   inputs replayed through the batch jobs.

Budget per program and per domain, logged the same way, so cost tracks progress.

## 7. What it doesn't do

| Gap | What a production version would add |
| --- | --- |
| One program, run in sequence | Parallel Analyzer runs per program with a concurrency cap |
| Telemetry written to local files, one thread | The OpenTelemetry SDK exporting to a backend, with context carried per task |
| API errors rely on the SDK's built-in retries | Timeouts per call, backoff with jitter, a breaker at the one door |
| State lives in memory | A checkpoint after each step so a run can resume |
| Rule matching is by keyword | A structured rule category per extracted rule |
| Fake mode tests the harness code only | Real runs on a schedule tell you about the model |
| Prompt caching is wired but doesn't engage at this size | It pays once the shared context is large |
