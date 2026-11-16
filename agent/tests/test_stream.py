import json

from crm_agent.build import build_agent
from crm_agent.stream import stream_ndjson
from fakes import ScriptedChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver

TYPES = {"start", "token", "think", "plan", "interrupt", "error"}


def _call(name, args, id_):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id_}])


def _tools():
    def contacts_get(contact_id: str) -> str:
        """Get a contact."""
        return "contact"

    return [StructuredTool.from_function(contacts_get)]


async def _run(script):
    agent = build_agent(ScriptedChatModel(script=script), _tools(), MemorySaver())
    config = {"configurable": {"thread_id": "t"}, "recursion_limit": 100}
    graph_input = {"messages": [{"role": "user", "content": "hi"}]}
    return [json.loads(line) async for line in stream_ndjson(agent, graph_input, config)]


async def test_event_order():
    events = await _run([AIMessage(content="Hello there")])
    assert events[0] == {"type": "start", "content": ""}
    assert {e["type"] for e in events} <= TYPES
    assert "".join(e["content"] for e in events if e["type"] == "token") == "Hello there"


def _todos(*items):
    return _call("write_todos", {"todos": [{"content": c, "status": s} for c, s in items]}, "x")


async def test_plan_only_on_change():
    first = [("a", "pending"), ("b", "pending")]
    script = [
        _todos(*first),
        _todos(*first),
        _todos(("a", "completed"), ("b", "pending")),
        AIMessage(content="done"),
    ]
    events = await _run(script)
    plans = [e["content"] for e in events if e["type"] == "plan"]
    assert plans == ["[pending] a\n[pending] b", "[completed] a\n[pending] b"]


async def test_think_from_subagent():
    script = [
        _call("task", {"description": "look up", "subagent_type": "researcher"}, "t1"),
        AIMessage(content="sub finding"),
        AIMessage(content="final answer"),
    ]
    events = await _run(script)
    think = [e["content"] for e in events if e["type"] == "think"]
    tokens = "".join(e["content"] for e in events if e["type"] == "token")
    assert think and "sub finding" in "".join(think)
    assert "sub finding" not in tokens
    assert "final answer" in tokens
