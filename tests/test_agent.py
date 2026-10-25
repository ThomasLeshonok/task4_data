import json
from types import SimpleNamespace as NS

from assistant.agent import Assistant

def tool_call(call_id, name, **args):
    return NS(id=call_id, function=NS(name=name, arguments=json.dumps(args)))

class ScriptedClient:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen = []

    def complete(self, messages, tools):
        self.seen.append([dict(m) for m in messages])
        return self.replies.pop(0)

def test_tool_results_reach_the_model(toolbox):
    client = ScriptedClient(
        NS(content=None, tool_calls=[tool_call("c1", "store_summary", store="STORE1")]),
        NS(content="STORE1 has 3221 unique users.", tool_calls=None),
    )
    answer = Assistant(client, toolbox).ask("How many unique users in STORE1?")
    assert answer.text == "STORE1 has 3221 unique users."
    assert answer.steps[0].tool == "store_summary"
    tool_message = client.seen[1][-1]
    assert tool_message["role"] == "tool" and '"unique_users": 3221' in tool_message["content"]

def test_bad_tool_call_returns_error_to_model(toolbox):
    client = ScriptedClient(
        NS(content=None, tool_calls=[tool_call("c1", "aggregate", store="STORE1", table="sales", metric="sum", column="price")]),
        NS(content="done", tool_calls=None),
    )
    answer = Assistant(client, toolbox).ask("Total price?")
    assert "error" in answer.steps[0].result
    assert "Available" in client.seen[1][-1]["content"]

def test_stops_after_max_rounds(toolbox):
    looping = NS(content=None, tool_calls=[tool_call("c", "list_stores")])
    answer = Assistant(ScriptedClient(*[looping] * 20), toolbox).ask("loop")
    assert "could not finish" in answer.text
