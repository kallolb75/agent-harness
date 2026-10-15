"""The one door to the model.

Every model call in the harness goes through LLM.call(). That single choke point is
what makes the controls possible:
  * cost:      each call is priced and appended to runs/<run_id>/tokens.jsonl
  * budget:    no call starts once the run's budget is spent
  * telemetry: each call is a span in runs/<run_id>/trace.jsonl, with its latency,
               token counts, cost and stop reason

Called by:  harness/orchestrator.py (the orchestrator's turns)
            harness/agents.py       (each worker attempt)
Calls:      the Anthropic Messages API, or fake/<agent>.json in --fake mode

Java/C# comparison: think of LLM as a gateway class that every service calls, with
logging and a circuit breaker on the way in.
"""

import json
import time
from pathlib import Path
from types import SimpleNamespace

from harness.config import PRICES
from harness.telemetry import Tracer

ROOT = Path(__file__).resolve().parent.parent


class BudgetExceeded(Exception):
    """Raised before a call when the run has already spent its budget."""


class LLM:
    def __init__(self, run_dir, budget_usd, fake=False, tracer=None):
        self.run_dir = run_dir
        self.budget_usd = budget_usd
        self.spent_usd = 0.0
        self.rows = []                      # one row per call, kept for the summary table
        self.log_path = run_dir / "tokens.jsonl"
        self.fake = fake
        self.fake_calls = {}                # agent name -> how many fake replies used so far
        # The tracer rides on the LLM object because every component already receives
        # `llm`. A larger system would pass a context object; here this keeps the
        # function signatures short.
        self.tracer = tracer or Tracer(run_dir / "trace.jsonl")
        if not fake:
            import anthropic                # imported here so --fake runs without the SDK or a key
            self.client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from the environment

    def call(self, agent, model, system, messages, max_tokens, tools=None):
        """Send one request and return the model's response object.

        Order of events, every time:
          1. open a telemetry span  (so even a refused call is recorded)
          2. budget check           (raise BudgetExceeded BEFORE spending anything)
          3. the call itself        (real API, or a scripted reply in --fake mode)
          4. price and log it       (tokens.jsonl, plus the span's attributes)
        """
        with self.tracer.span("llm.call", agent=agent, model=model, max_tokens=max_tokens,
                              turn_messages=len(messages)) as span:
            # Cost control 1: the budget is checked BEFORE the call. The worst overshoot
            # is therefore one call, and max_tokens bounds that call's output.
            if self.spent_usd >= self.budget_usd:
                raise BudgetExceeded(
                    f"{agent}: ${self.spent_usd:.4f} spent of ${self.budget_usd:.2f}, stopping before the call"
                )

            request = {
                "model": model,
                "system": system,
                "messages": messages,
                "max_tokens": max_tokens,
            }
            if tools:
                request["tools"] = tools

            if self.fake:
                response = self._fake_response(agent)
            else:
                response = self.client.messages.create(**request)

            row = self._log(agent, model, response.usage)
            span.set(input_tokens=row["input"], output_tokens=row["output"],
                     cache_read=row["cache_read"], cache_write=row["cache_write"],
                     cost_usd=row["cost_usd"], run_total_usd=row["run_total_usd"],
                     stop_reason=response.stop_reason)
            return response

    def _log(self, agent, model, usage):
        """Cost control 2: price every call and append it to runs/<id>/tokens.jsonl."""
        # getattr(..., 0) because the cache fields can be missing or None.
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        price = PRICES[model]
        cost = (
            usage.input_tokens * price["input"]
            + usage.output_tokens * price["output"]
            + cache_write * price["cache_write"]
            + cache_read * price["cache_read"]
        ) / 1_000_000
        self.spent_usd += cost

        row = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "agent": agent,
            "model": model,
            "input": usage.input_tokens,
            "output": usage.output_tokens,
            "cache_write": cache_write,
            "cache_read": cache_read,
            "cost_usd": round(cost, 6),
            "run_total_usd": round(self.spent_usd, 6),
        }
        self.rows.append(row)
        with open(self.log_path, "a") as f:   # "a" = append, like FileWriter(path, true) in Java
            f.write(json.dumps(row) + "\n")
        return row

    def cost_table(self):
        """A per-agent summary, printed at the end of a run."""
        totals = {}
        for row in self.rows:
            t = totals.setdefault(row["agent"], {"calls": 0, "input": 0, "output": 0, "cost": 0.0})
            t["calls"] += 1
            t["input"] += row["input"] + row["cache_write"] + row["cache_read"]
            t["output"] += row["output"]
            t["cost"] += row["cost_usd"]
        lines = [f"{'agent':<14}{'calls':>6}{'in tok':>9}{'out tok':>9}{'cost $':>10}"]
        for agent, t in totals.items():
            lines.append(f"{agent:<14}{t['calls']:>6}{t['input']:>9}{t['output']:>9}{t['cost']:>10.4f}")
        lines.append(f"{'run total':<38}{self.spent_usd:>10.4f}   (budget {self.budget_usd:.2f})")
        return "\n".join(lines)

    def _fake_response(self, agent):
        """Offline mode: replay a scripted reply from fake/<agent>.json.

        Lets you run the whole harness, and its tests, with no API key and no cost.
        The scripted replies have the same shape as real ones, so nothing downstream
        knows the difference.
        """
        script = json.loads((ROOT / "fake" / f"{agent}.json").read_text())
        n = self.fake_calls.get(agent, 0)
        self.fake_calls[agent] = n + 1
        reply = script[min(n, len(script) - 1)]

        # A worker's scripted reply is a JSON object; the model would send it as text.
        if "json" in reply:
            content = [{"type": "text", "text": json.dumps(reply["json"], indent=2)}]
        else:
            content = reply["content"]

        # SimpleNamespace turns a dict into an object with attributes, so the code
        # can say block.type the same way it does with a real SDK response.
        return SimpleNamespace(
            stop_reason=reply["stop_reason"],
            content=[SimpleNamespace(**block) for block in content],
            usage=SimpleNamespace(**reply["usage"]),
        )
