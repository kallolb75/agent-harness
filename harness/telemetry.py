"""Telemetry: a trace of every step in a run, written to runs/<run_id>/trace.jsonl.

A run leaves three records behind. Each answers a different question:

    tokens.jsonl   What did each model call cost?             harness/llm.py
    trace.jsonl    What happened, in what order, how long?    this file
    result.json    What did the agents produce, and how good? run.py + evals/check.py

A TRACE is a tree of SPANS. A span is one unit of work: it has a name, a start, a
duration, a status (ok or error) and attributes (agent, model, tokens, cost...).
Every span records its parent, so the tree can be rebuilt afterwards:

    run
    └─ orchestrator.turn 1
       ├─ llm.call  orchestrator  claude-sonnet-5-5   912 in / 48 out   stop=tool_use
       └─ tool.call run_analyzer
          └─ worker analyzer
             └─ worker.attempt 1
                └─ llm.call  analyzer  claude-sonnet-5-5  1688 in / 842 out  stop=end_turn

These are the same ideas as OpenTelemetry (trace id, span id, parent id,
attributes, status). This version uses only the standard library so it runs
anywhere. Moving to the OpenTelemetry SDK later means replacing this class; the
call sites (`with tracer.span(...)`) stay the same.

Who uses it:
    run.py creates the Tracer and hands it to LLM, so every component that already
    receives `llm` can reach it as `llm.tracer`.

Read a finished trace as a tree:
    uv run python -m harness.telemetry runs/<run_id>
"""

import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path


class Span:
    """One unit of work. Created by Tracer.span(); you only call .set() on it."""

    def __init__(self, trace_id, span_id, parent_id, name, attrs):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_id = parent_id
        self.name = name
        self.attrs = dict(attrs)
        self.status = "ok"
        self.started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.duration_ms = None

    def set(self, **attrs):
        """Add what you learned while the work ran: tokens, cost, the tool's result."""
        self.attrs.update(attrs)

    def to_dict(self):
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "attrs": self.attrs,
        }


class Tracer:
    """Hands out spans and writes each one to trace.jsonl when it ends.

    path=None keeps spans in memory only. echo=True prints each step as it starts
    and ends, which is the easiest way to watch the calls happen (run.py --trace).
    """

    def __init__(self, path=None, trace_id="run", echo=False):
        self.path = Path(path) if path else None
        self.trace_id = trace_id
        self.echo = echo
        self.spans = []          # finished spans, in the order they ENDED
        self._open = []          # spans still running; the last one is the current parent
        self._count = 0          # span ids are numbered in the order spans START

    @contextmanager
    def span(self, name, **attrs):
        """Time a block of work and record it as a child of whatever span is open.

            with tracer.span("llm.call", agent="analyzer") as span:
                response = ...
                span.set(input_tokens=response.usage.input_tokens)

        If the block raises, the span is marked status=error with the message, and
        the exception carries on up. Telemetry records failures; it never hides them.
        """
        self._count += 1
        parent = self._open[-1].span_id if self._open else None
        span = Span(self.trace_id, f"s{self._count:03d}", parent, name, attrs)
        depth = len(self._open)
        self._print(depth, "▶", name, attrs)

        self._open.append(span)
        started = time.perf_counter()
        try:
            yield span
        except Exception as err:
            span.status = "error"
            span.set(error=f"{type(err).__name__}: {err}")
            raise
        finally:
            span.duration_ms = round((time.perf_counter() - started) * 1000, 1)
            self._open.pop()
            self.spans.append(span)
            self._write(span)
            outcome = {k: v for k, v in span.attrs.items() if k not in attrs}
            self._print(depth, "✗" if span.status == "error" else "✓", name,
                        outcome, span.duration_ms)

    def _write(self, span):
        if self.path:
            with open(self.path, "a") as f:
                f.write(json.dumps(span.to_dict()) + "\n")

    def _print(self, depth, mark, name, attrs, ms=None):
        if not self.echo:
            return
        detail = "  ".join(f"{k}={_short(v)}" for k, v in attrs.items())
        timing = f"  ({ms} ms)" if ms is not None else ""
        print(f"{'   ' * depth}{mark} {name}  {detail}{timing}")


def _short(value, limit=70):
    text = value if isinstance(value, str) else json.dumps(value)
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[:limit - 3] + "..."


# ---------------------------------------------------------------- reading a trace

def load(path):
    """Read trace.jsonl back into a list of span dicts, in the order they started."""
    spans = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    return sorted(spans, key=lambda s: s["span_id"])


def render_tree(spans):
    """Turn a list of span dicts into the indented tree shown in the docstring."""
    children = {}
    for s in spans:
        children.setdefault(s["parent_id"], []).append(s)

    lines = []

    def walk(span, prefix, last):
        branch = "" if span["parent_id"] is None else ("└─ " if last else "├─ ")
        lines.append(f"{prefix}{branch}{_label(span)}")
        kids = children.get(span["span_id"], [])
        deeper = prefix + ("" if span["parent_id"] is None else ("   " if last else "│  "))
        for i, kid in enumerate(kids):
            walk(kid, deeper, i == len(kids) - 1)

    roots = children.get(None, [])
    for i, root in enumerate(roots):
        walk(root, "", i == len(roots) - 1)
    return "\n".join(lines)


def summarize(spans):
    """The numbers you want first: how many calls, tokens, cost, time, errors."""
    calls = [s for s in spans if s["name"] == "llm.call"]
    roots = [s for s in spans if s["parent_id"] is None]
    return {
        "model_calls": len(calls),
        "input_tokens": sum(s["attrs"].get("input_tokens", 0) for s in calls),
        "output_tokens": sum(s["attrs"].get("output_tokens", 0) for s in calls),
        "cost_usd": round(sum(s["attrs"].get("cost_usd", 0) for s in calls), 6),
        "wall_ms": round(sum(s["duration_ms"] or 0 for s in roots), 1),
        "model_ms": round(sum(s["duration_ms"] or 0 for s in calls), 1),
        "errors": [f"{s['name']}: {s['attrs'].get('error')}" for s in spans if s["status"] == "error"],
    }


def _label(span):
    a = span["attrs"]
    name = span["name"]
    if name == "llm.call":
        text = (f"llm.call  {a.get('agent')}  {a.get('model')}  "
                f"{a.get('input_tokens', '?')} in / {a.get('output_tokens', '?')} out  "
                f"${a.get('cost_usd', 0):.4f}  stop={a.get('stop_reason', '?')}")
    elif name == "tool.call":
        text = f"tool.call {a.get('tool')}  ->  {_short(a.get('result', ''), 60)}"
    elif name in ("orchestrator.turn", "turn"):
        text = f"{name} {a.get('turn')}"
    elif name == "worker":
        text = f"worker {a.get('agent')}"
    elif name == "worker.attempt":
        text = f"worker.attempt {a.get('attempt')}" + ("" if a.get("valid", True) else f"  invalid: {a.get('problem')}")
    elif name == "run":
        text = f"run {span['trace_id']}  {a.get('source', a.get('use_case', ''))}"
    elif name == "eval":
        text = f"eval  drift={a.get('verdict')}  gate={a.get('gate')}"
    else:
        text = name
    if span["status"] == "error":
        text += f"  ERROR {a.get('error')}"
    return f"{text}  [{span['duration_ms']} ms]"


if __name__ == "__main__":
    target = Path(sys.argv[1])
    trace_file = target / "trace.jsonl" if target.is_dir() else target
    spans = load(trace_file)
    print(render_tree(spans))
    print()
    for key, value in summarize(spans).items():
        print(f"{key:<15}{value}")
