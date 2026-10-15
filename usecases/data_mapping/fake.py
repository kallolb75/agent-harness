"""A stand-in for the Anthropic client, so the data mapping agent runs offline for free.

Same shape as the real client: client.messages.create(...) returns an object with
.stop_reason, .content and .usage. It replays the replies below in order.

The script shows three things worth watching:
    reply 2 maps balance with copy, missing that BAL_AMT is in cents
    reply 3 reconciles and tries to submit in the same turn: reconciliation FAILS
           (the total is 100 times too large) and the harness REFUSES the submit
    reply 4 is the model reading the failure and fixing the mapping
"""

from types import SimpleNamespace


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool(tool_id, tool_name, **inputs):
    return SimpleNamespace(type="tool_use", id=tool_id, name=tool_name, input=inputs)


def reply(stop_reason, content, tokens_in, tokens_out):
    return SimpleNamespace(stop_reason=stop_reason, content=content,
                           usage=SimpleNamespace(input_tokens=tokens_in, output_tokens=tokens_out))


def mapping(balance_transform):
    return [
        {"target": "customer_id", "source": "CUST_ID", "transform": "to_int"},
        {"target": "first_name", "source": "CUST_NM", "transform": "name_first"},
        {"target": "last_name", "source": "CUST_NM", "transform": "name_last"},
        {"target": "birth_date", "source": "BIRTH_DT", "transform": "date_yyyymmdd"},
        {"target": "status", "source": "STATUS_CD", "transform": "status_code"},
        {"target": "balance", "source": "BAL_AMT", "transform": balance_transform},
        {"target": "state", "source": "STATE_CD", "transform": "copy"},
    ]


SCRIPT = [
    reply("tool_use", [text("Reading both schemas."),
                       tool("t1", "get_source_schema"),
                       tool("t2", "get_target_schema")], 900, 50),

    reply("tool_use", [text("Proposing a field-by-field mapping."),
                       tool("t3", "propose_mapping", mapping=mapping("copy"))], 1800, 320),

    reply("tool_use", [text("Reconciling, then submitting."),
                       tool("t4", "reconcile"),
                       tool("t5", "submit_mapping")], 2300, 60),

    reply("tool_use", [text("The balance total is 100 times the control total: BAL_AMT is in "
                            "cents. Switching balance to cents_to_dollars."),
                       tool("t6", "propose_mapping", mapping=mapping("cents_to_dollars"))], 2700, 340),

    reply("tool_use", [text("Reconciling the corrected mapping."),
                       tool("t7", "reconcile")], 3200, 40),

    reply("tool_use", [text("All four checks pass. Submitting."),
                       tool("t8", "submit_mapping")], 3500, 40),

    reply("end_turn", [text("CUSTMAST is mapped to customers: 7 fields, all reconciled against "
                            "the legacy control totals (8 rows, $61,187.14, 5 active, 2 inactive, "
                            "1 closed). The first attempt treated the balance as dollars; "
                            "reconciliation caught it.")], 3700, 120),
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
