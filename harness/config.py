"""Settings that change more often than code: prices, the budget, the turn cap.

Kept in one file so a price change is a one-line edit and a reviewer can see
every limit the harness runs under without reading the logic.
"""

# USD per million tokens. Source: platform.claude.com/docs/en/about-claude/pricing,
# checked 2026-10-09. Prices change; re-check before you quote a number.
PRICES = {
    "claude-opus-5-5":   {"input": 4.00, "output": 20.00, "cache_write": 5.000, "cache_read": 0.20},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_write": 2.500, "cache_read": 0.10},
    "claude-haiku-5-5":  {"input": 0.10, "output": 0.50,  "cache_write": 0.125, "cache_read": 0.01},
}

# The most one run may spend. Checked before every model call.
DEFAULT_BUDGET_USD = 0.50

# The most times the orchestrator may go round its loop before the harness stops it.
# A loop with no cap is how an agent burns a budget overnight.
MAX_ORCHESTRATOR_TURNS = 6

# The most times the analyzer may run in one intake. A second pass can clear up
# code it could not follow; a third rarely does, and the question goes to a human.
MAX_ANALYZER_RUNS = 2

# Every agent the harness knows. Each one has a context file in agents/<name>.md.
AGENT_NAMES = ["orchestrator", "analyzer", "test_writer"]
