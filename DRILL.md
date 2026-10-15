# The drill

Four sessions, about four and a half hours in all. The goal: you can open a blank
file and write a working harness loop in 20 minutes, and you can walk someone through
this harness for 5 minutes and answer the questions in WALKTHROUGH.md section 5
without notes.

## Session 1 · 75 min · run it, read it

1. `uv sync`, then `uv run run.py legacy/ORDPRICE.cbl --fake --trace`. Read what it
   prints: every step as it happens, then the summary, the cost table, the eval report
   and the trace tree.
2. `uv run pytest`. All green.
3. Open `runs/<id>/tokens.jsonl`. One line per call. Find the analyzer's line and work
   out its cost by hand: input tokens x $2 + output tokens x $10, per million. It
   should match.
4. Read in this order, with [docs/CALL_FLOW.md](docs/CALL_FLOW.md) open beside you:
   `harness/llm.py`, `harness/orchestrator.py`, `harness/agents.py`,
   `harness/context.py`, `harness/telemetry.py`. Write down every line you can't
   explain, and don't move on until each one is answered.

## Session 2 · 60 min · the real run

1. Set `ANTHROPIC_API_KEY`. `uv run run.py legacy/ORDPRICE.cbl`. Note the cost.
2. Open `runs/<id>/result.json`. Read the rules the Analyzer found against
   `legacy/ORDPRICE.cbl`. Did it catch that the fee is taxed? That the discounts compound?
3. Read the eval. **If test_accuracy drifted or fell below the floor**, the cheaper
   model got the arithmetic wrong. That is the most useful thing that can happen here:
   - Change `model:` in `agents/test_writer.md` to `claude-sonnet-5-5`. Run again.
   - The report now names the model change. Compare cost and test_accuracy between the
     two runs and write the trade-off in one sentence.
   - Keep whichever model you can defend.
4. When a run is one you'd stand behind:
   `uv run python -m evals.check runs/<id>/result.json --set-baseline`.

## Session 3 · 60 min · break it on purpose

Each one: predict what happens, run it, check the prediction, put it back.

1. **Budget.** `--budget 0.01`. Where does it stop, and how far past 0.01 did it get?
   Find the refused call in the trace tree.
2. **Drift from a prompt edit.** In `agents/analyzer.md`, delete "and the ORDER the
   rules are applied in, because order changes the answer". Run. Does the eval flag a
   metric? It may not: the model can still get it right without being told. What does
   "changed since baseline" say either way?
3. **Order control.** In `agents/orchestrator.md`, tell it to call `run_test_writer`
   first. Run. Find the refused `tool.call` in the trace.
4. **Eval honesty.** In `evals/check.py`, replace the drift comparison
   `value < baseline["metrics"][m] - TOLERANCE` with `False`. Run pytest. Tests must
   fail. Then do the same to the quality gate. A check that can't fail is decoration.

## Session 4 · 75 min · rebuild from blank

1. **Round 1, 30 min.** New file `drill/mine.py`. No peeking. Write a harness with one
   model, one tool (`lookup_tax_rate`), the loop, a turn cap and a token count. Run it.
   Checkpoints, in order:
   - [ ] client, model name, a `TOOLS` list with one tool and its `input_schema`
   - [ ] a `run_tool(name, args)` function
   - [ ] `messages` starts with the user question
   - [ ] the loop: call, add up tokens, append the assistant turn
   - [ ] fail if `stop_reason` is `"max_tokens"`
   - [ ] stop when `stop_reason` is not `"tool_use"` and return the text
   - [ ] run each `tool_use` block, send back `tool_result` blocks with the matching `tool_use_id`
   - [ ] raise after the turn cap

   Then compare with `drill/answer_key.py`. Write down what you missed.
2. **Round 2, 20 min.** Delete `mine.py`. Do it again. Target: no misses.
3. **The 5-minute walkthrough.** Say it out loud and record it: the problem, the four
   controls, one number from your real run, what changes at the scale of a real estate
   (WALKTHROUGH.md section 6). Play it back once.
