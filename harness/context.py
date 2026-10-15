"""Context engineering: what each agent sees, and nothing more.

An agent's context is built from three things, in this order:
  1. AGENTS.md, the shared project rules every agent follows
  2. agents/<name>.md, that agent's own instructions and settings
  3. the inputs its file declares (the source, the analysis), pulled from run state

The agent file DECLARES what it loads (the `inputs:` line). The harness does not
hardcode it. Change what an agent sees by editing its file, not the Python.

Called by: harness/orchestrator.py and harness/agents.py (load_agent, system_prompt,
           build_inputs); run.py (prompt_hash, prompt_hashes, for the run record)
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_agent(name):
    """Read agents/<name>.md: settings from the header, instructions from the body.

    The file looks like:
        ---
        model: claude-sonnet-5-5
        max_tokens: 3000
        inputs: source
        ---
        You are the Analyzer...
    """
    text = (ROOT / "agents" / f"{name}.md").read_text()
    _, header, body = text.split("---", 2)    # split on the first two '---' only

    settings = {}
    for line in header.strip().splitlines():
        key, value = line.split(":", 1)
        settings[key.strip()] = value.strip()

    settings["max_tokens"] = int(settings["max_tokens"])
    settings["inputs"] = _as_list(settings.get("inputs", ""))
    settings["requires"] = _as_list(settings.get("requires", ""))
    settings["instructions"] = body.strip()
    return settings


def _as_list(value):
    """'source, analysis' -> ['source', 'analysis']"""
    return [item.strip() for item in value.split(",") if item.strip()]


def system_prompt(agent):
    """The stable part of the context: shared rules plus the agent's instructions.

    It is marked for prompt caching. When the same agent is called again within a
    few minutes, this prefix is read from cache at a fraction of the input price.
    (Below the model's minimum cacheable length, caching is silently skipped.)
    """
    shared = (ROOT / "AGENTS.md").read_text()
    return [{
        "type": "text",
        "text": shared + "\n\n" + agent["instructions"],
        "cache_control": {"type": "ephemeral"},
    }]


def build_inputs(agent, state):
    """The variable part: each declared input, wrapped in a tag the agent can refer to."""
    parts = []
    for name in agent["inputs"]:
        value = state[name]
        if not isinstance(value, str):
            value = json.dumps(value, indent=2)
        parts.append(f"<{name}>\n{value}\n</{name}>")
    return "\n\n".join(parts)


def _context_files():
    return [ROOT / "AGENTS.md", *sorted((ROOT / "agents").glob("*.md"))]


def prompt_hash():
    """One fingerprint for ALL context files together. Stored with each run so the
    drift check can tell 'the prompts changed' apart from 'the prompts did not change,
    the output did'."""
    h = hashlib.sha256()
    for path in _context_files():
        h.update(path.read_bytes())
    return h.hexdigest()[:12]


def prompt_hashes():
    """One fingerprint PER context file, so the drift report can name the file that
    changed (agents/analyzer.md) instead of only saying 'the prompts changed'."""
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()[:12]
            for path in _context_files()}
