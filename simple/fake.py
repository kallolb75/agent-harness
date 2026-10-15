"""A stand-in for the Anthropic client, so the triage agent runs offline for free.

FakeClient has the same shape as the real client: client.messages.create(...)
returns an object with .stop_reason, .content and .usage. It ignores what it is
sent and replays the replies below in order. Nothing in triage.py knows the
difference, which is the point: the harness code runs for real, only the model
is swapped out.

The script shows three things worth watching:
    reply 2 asks for five tools in ONE turn (parallel tool requests)
    reply 3 uses a disposition that is not allowed; the harness refuses it in code
    reply 4 is the model correcting itself after reading the error
"""

from types import SimpleNamespace


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool(tool_id, tool_name, **inputs):
    return SimpleNamespace(type="tool_use", id=tool_id, name=tool_name, input=inputs)


def reply(stop_reason, content, tokens_in, tokens_out):
    return SimpleNamespace(stop_reason=stop_reason, content=content,
                           usage=SimpleNamespace(input_tokens=tokens_in, output_tokens=tokens_out))


SCRIPT = [
    reply("tool_use", [text("I'll start with the inventory."),
                       tool("t1", "list_apps")], 850, 40),

    reply("tool_use", [text("Five applications. I'll read each one before deciding."),
                       tool("t2", "get_app", name="ORDER-ENTRY"),
                       tool("t3", "get_app", name="HR-REPORTS"),
                       tool("t4", "get_app", name="CLAIMS-PORTAL"),
                       tool("t5", "get_app", name="PRICING-ENGINE"),
                       tool("t6", "get_app", name="DOC-ARCHIVE")], 1100, 210),

    reply("tool_use", [text("Recording a decision for each application."),
                       tool("t7", "record_decision", name="ORDER-ENTRY", disposition="refactor",
                            reason="Core revenue system that must change weekly and is losing its last "
                                   "experts, so extract pricing and order services behind a strangler facade."),
                       tool("t8", "record_decision", name="HR-REPORTS", disposition="decommission",
                            reason="Every report now lives in the HR SaaS and the server is out of support."),
                       tool("t9", "record_decision", name="CLAIMS-PORTAL", disposition="replatform",
                            reason="Healthy, tested code whose costs are the WebLogic licence and manual "
                                   "deploys, so containerize it onto a managed runtime with CI/CD."),
                       tool("t10", "record_decision", name="PRICING-ENGINE", disposition="retain",
                            reason="Already cloud-native and meeting its service levels, so changing it adds "
                                   "risk for no gain."),
                       tool("t11", "record_decision", name="DOC-ARCHIVE", disposition="rehost",
                            reason="Stable and rarely changed, but the data center lease ends in nine months, "
                                   "so move it to cloud VMs now and revisit later.")], 2900, 420),

    reply("tool_use", [text("Decommission is not an allowed value; the matching disposition is retire."),
                       tool("t12", "record_decision", name="HR-REPORTS", disposition="retire",
                            reason="Every report now lives in the HR SaaS and the server is out of support, "
                                   "so switch it off once no one is still using it.")], 3600, 90),

    reply("end_turn", [text("All five applications have a decision: one refactor, one retire, one "
                            "replatform, one retain and one rehost. ORDER-ENTRY is the only one that "
                            "needs a multi-quarter program; the rest are weeks of work.")], 3800, 160),
]


class FakeClient:
    """Replays SCRIPT, one reply per call. A fresh client starts from the first reply."""

    def __init__(self):
        self.calls = 0
        self.messages = self          # so client.messages.create(...) works

    def create(self, **request):
        response = SCRIPT[min(self.calls, len(SCRIPT) - 1)]
        self.calls += 1
        return response
