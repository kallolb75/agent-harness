"""The orchestrator: a model that decides which worker to call next.

The workers are exposed to it as TOOLS. It reads the task, asks for a tool, the
harness runs that worker, and the result goes back to it. It loops until the
model stops asking for tools or the harness stops it.

This loop is the heart of every agent harness:

    call the model
    if it stopped because it hit max_tokens: fail, the reply is incomplete
    if it did not ask for a tool:            done, return its text
    for each tool it asked for:              run it, collect the result
    send all the results back in one turn, go round again

Who calls what (see docs/CALL_FLOW.md for the full picture):

    run.py
      └─ run_orchestrator()                         this file
           ├─ llm.call("orchestrator", ..., tools)  harness/llm.py
           └─ dispatch()                            this file, once per tool request
                └─ run_worker("analyzer" | "test_writer")   harness/agents.py
                     └─ llm.call(worker, ...)              harness/llm.py

Three design choices to defend:
  * Workers' full outputs go into STATE, not into the orchestrator's conversation.
    The orchestrator gets a one-line summary. Its context stays small, and the
    Test-writer reads the Analyzer's real output, not the orchestrator's retelling.
  * The harness enforces the rules. run_test_writer before run_analyzer is refused in
    code, and so is a third analyzer run. The prompt states both rules too, but a
    prompt asking nicely is not a control.
  * The loop has a turn cap (MAX_ORCHESTRATOR_TURNS) and every call passes the
    budget check in LLM.call.
"""

from harness.agents import run_worker
from harness.config import MAX_ANALYZER_RUNS
from harness.context import load_agent, system_prompt

# What the orchestrator model is told it can do. Each tool is a name, a description
# (the model reads it as an instruction) and a JSON Schema for its input.
TOOLS = [
    {
        "name": "run_analyzer",
        "description": "Ask the Analyzer agent to extract business rules from the legacy source. "
                       "Pass `focus` only on a re-run, naming what to look at again.",
        "input_schema": {
            "type": "object",
            "properties": {"focus": {"type": "string"}},
        },
    },
    {
        "name": "run_test_writer",
        "description": "Ask the Test-writer agent for parity tests built from the stored analysis. "
                       "Needs run_analyzer to have run first.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def run_orchestrator(state, llm, max_turns):
    """Run the tool-use loop until the orchestrator finishes. Returns its final text.

    Called by: run.py
    Calls:     llm.call() once per turn, dispatch() once per tool request
    Raises:    RuntimeError if the turn cap is hit or a reply is cut off at max_tokens;
               BudgetExceeded (from llm.call) if the money runs out
    """
    agent = load_agent("orchestrator")
    tracer = llm.tracer

    # The whole conversation. The API keeps no state between calls, so this list is
    # sent in full every turn. It grows by two entries per turn: the model's reply
    # and the tool results we send back.
    messages = [{
        "role": "user",
        "content": f"Modernization intake for {state['source_name']}. "
                   "Get its business rules extracted, then get parity tests written.",
    }]

    for turn in range(1, max_turns + 1):
        with tracer.span("orchestrator.turn", turn=turn):
            response = llm.call("orchestrator", agent["model"], system_prompt(agent),
                                messages, agent["max_tokens"], tools=TOOLS)

            # Keep the model's turn, tool requests included. The API rejects a
            # tool_result that does not follow the tool_use it answers.
            messages.append({"role": "assistant", "content": [to_dict(b) for b in response.content]})

            if response.stop_reason == "max_tokens":
                # The reply was cut off. Treating it as finished would return a
                # half-written answer as if it were complete.
                raise RuntimeError("orchestrator reply was cut off at max_tokens; "
                                   "raise max_tokens in agents/orchestrator.md")

            if response.stop_reason != "tool_use":
                # end_turn (or stop_sequence): the model has stopped asking for tools.
                return "".join(b.text for b in response.content if b.type == "text")

            # The model may ask for several tools in one turn. Run each one, and send
            # every result back together, each tagged with the id of its request.
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    with tracer.span("tool.call", tool=block.name, tool_use_id=block.id,
                                     input=block.input) as span:
                        output = dispatch(block.name, block.input, state, llm)
                        span.set(result=output, refused=output.startswith("Refused"))
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
            messages.append({"role": "user", "content": results})

    raise RuntimeError(f"orchestrator did not finish within {max_turns} turns")


def dispatch(tool_name, args, state, llm):
    """Run the worker the orchestrator asked for. Returns a short text summary.

    Called by: run_orchestrator(), once per tool_use block
    Calls:     run_worker() in harness/agents.py
    Writes:    state["analysis"] or state["tests"], the worker's FULL output

    Whatever this returns is ALL the orchestrator learns about the work. A refusal is
    returned as text, not raised, because it is information the model should act on.
    """
    if tool_name == "run_analyzer":
        if state["analyzer_runs"] >= MAX_ANALYZER_RUNS:
            return (f"Refused: the analyzer has run {MAX_ANALYZER_RUNS} times. "
                    "Send what is still unclear to a human as an open question.")
        task = "Extract every business rule from the source."
        if args.get("focus"):
            task += f" On this pass, look again carefully at: {args['focus']}"
        state["analysis"] = run_worker("analyzer", task, state, llm)
        state["analyzer_runs"] += 1
        rules = state["analysis"]["rules"]
        questions = state["analysis"]["open_questions"]
        return (f"Analysis stored: {len(rules)} rules ({', '.join(r['id'] for r in rules)}). "
                f"Open questions: {questions or 'none'}. Analyzer runs so far: {state['analyzer_runs']}.")

    if tool_name == "run_test_writer":
        if "analysis" not in state:
            return "Refused: no analysis stored yet. Call run_analyzer first."
        state["tests"] = run_worker("test_writer", "Write parity tests for these rules.", state, llm)
        return f"Tests stored: {len(state['tests']['tests'])} cases."

    return f"Unknown tool: {tool_name}"


def to_dict(block):
    """Turn a response block back into the plain dict the API accepts on the next turn.

    Real SDK blocks and fake-mode blocks are different Python types; converting both
    to plain dicts means the rest of the loop never needs to know which mode it is in.
    """
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    # A real model may think before it asks for a tool. The API requires those thinking
    # blocks to be sent back unchanged on the next turn, signature included.
    if block.type == "thinking":
        return {"type": "thinking", "thinking": block.thinking, "signature": block.signature}
    if block.type == "redacted_thinking":
        return {"type": "redacted_thinking", "data": block.data}
    raise ValueError(f"unexpected block type {block.type}")
