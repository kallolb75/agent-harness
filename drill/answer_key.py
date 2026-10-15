"""ANSWER KEY. Don't open this until you've tried the drill (DRILL.md, session 4) from a blank file.

The smallest complete agent harness: one model, one tool, the loop, a turn cap and a
token count. About 40 lines. This is the shape a live coding round asks for, and it
is the same loop as harness/orchestrator.py with the workers taken out.

    uv run python drill/answer_key.py
"""

import anthropic

client = anthropic.Anthropic()
MODEL = "claude-haiku-5-5"
MAX_TURNS = 5

TAX_RATES = {"TX": 0.0625, "CA": 0.0725}

TOOLS = [{
    "name": "lookup_tax_rate",
    "description": "Sales tax rate for a two-letter US state code, as a decimal.",
    "input_schema": {
        "type": "object",
        "properties": {"state": {"type": "string"}},
        "required": ["state"],
    },
}]


def run_tool(name, args):
    if name == "lookup_tax_rate":
        return str(TAX_RATES.get(args["state"], 0.05))
    return f"unknown tool {name}"


def ask(question):
    messages = [{"role": "user", "content": question}]
    tokens_in = tokens_out = 0

    for turn in range(MAX_TURNS):
        response = client.messages.create(model=MODEL, max_tokens=500, tools=TOOLS, messages=messages)
        tokens_in += response.usage.input_tokens
        tokens_out += response.usage.output_tokens
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "max_tokens":
            raise RuntimeError("reply cut off at max_tokens")
        if response.stop_reason != "tool_use":
            print(f"turns={turn + 1} tokens in={tokens_in} out={tokens_out}")
            return "".join(b.text for b in response.content if b.type == "text")

        results = []
        for block in response.content:
            if block.type == "tool_use":
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": run_tool(block.name, block.input),
                })
        messages.append({"role": "user", "content": results})

    raise RuntimeError(f"no answer within {MAX_TURNS} turns")


if __name__ == "__main__":
    print(ask("What is the sales tax on a $200 order shipped to California?"))
