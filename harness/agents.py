"""Worker agents: one model call that must come back as a JSON object.

A worker gets a fresh context every time: the shared rules, its own instructions,
its declared inputs and one task. It never sees the orchestrator's conversation.
That isolation keeps each worker's input small (cheaper) and focused (fewer
distractions), and it means a worker's output depends only on what it was given.

Called by: harness/orchestrator.py, dispatch()
Calls:     harness/context.py to build the context, harness/llm.py to call the model
"""

import json

from harness.context import build_inputs, load_agent, system_prompt


def run_worker(name, task, state, llm):
    """Run one worker and return its JSON output as a dict.

    Two attempts. If the first reply is not valid JSON with the required keys, the
    reply and the error go back to the model once. A third try rarely fixes what two
    did not, and every try costs money.
    """
    agent = load_agent(name)
    user_text = task + "\n\n" + build_inputs(agent, state)
    messages = [{"role": "user", "content": user_text}]

    with llm.tracer.span("worker", agent=name, inputs=agent["inputs"]) as worker_span:
        for attempt in (1, 2):
            with llm.tracer.span("worker.attempt", agent=name, attempt=attempt) as span:
                response = llm.call(name, agent["model"], system_prompt(agent), messages, agent["max_tokens"])
                text = "".join(block.text for block in response.content if block.type == "text")

                if response.stop_reason == "max_tokens":
                    # Retrying with the same cap would be cut off again. Fail with the fix.
                    raise RuntimeError(f"{name} reply was cut off at max_tokens; "
                                       f"raise max_tokens in agents/{name}.md")
                try:
                    result = parse_json(text)
                    missing = [key for key in agent["requires"] if key not in result]
                    if missing:
                        raise ValueError(f"missing required keys {missing}")
                    span.set(valid=True)
                    worker_span.set(attempts=attempt)
                    return result
                except ValueError as err:          # json.JSONDecodeError is a ValueError too
                    span.set(valid=False, problem=str(err))
                    messages.append({"role": "assistant", "content": text})
                    messages.append({"role": "user", "content": f"That reply was not valid: {err}. Reply with the JSON object only."})

        raise RuntimeError(f"{name} did not return valid JSON in two attempts")


def parse_json(text):
    """Pull the JSON object out of the reply, even if the model wrapped it in prose
    or a ```json fence."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in the reply")
    return json.loads(text[start:end + 1])
