import pytest
from crm_agent.build import build_agent, is_write_tool
from fakes import ScriptedChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command


def test_is_write_tool():
    assert is_write_tool("deals_move_stage")
    assert is_write_tool("contacts_merge")
    assert not is_write_tool("deals_list_by_stage")
    assert not is_write_tool("reports_overdue_tasks")


def _call(name, args, id_):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id_}])


def _tools(calls):
    def deals_get(deal_id: str) -> str:
        """Get a deal."""
        return "deal"

    def deals_update(deal_id: str, title: str) -> str:
        """Update a deal title."""
        calls.append(deal_id)
        return "updated"

    return [StructuredTool.from_function(f) for f in (deals_get, deals_update)]


def _agent(calls, script):
    return build_agent(ScriptedChatModel(script=script), _tools(calls), MemorySaver())


def _cfg(tid):
    return {"configurable": {"thread_id": tid}, "recursion_limit": 100}


def _script():
    return [
        _call("search_tools", {"query": "update deal"}, "c1"),
        _call("deals_update", {"deal_id": "d1", "title": "x"}, "c2"),
        AIMessage(content="done"),
    ]


@pytest.mark.parametrize("decision, ran", [({"type": "approve"}, 1), ({"type": "reject"}, 0)])
async def test_write_tool_interrupts(decision, ran):
    calls = []
    agent = _agent(calls, _script())
    cfg = _cfg("t")
    out = await agent.ainvoke({"messages": [{"role": "user", "content": "rename d1"}]}, cfg)
    reqs = out["__interrupt__"][0].value["action_requests"]
    assert [r["name"] for r in reqs] == ["deals_update"]
    assert calls == []
    await agent.ainvoke(Command(resume={"decisions": [decision]}), cfg)
    assert len(calls) == ran


async def test_skills_read_only():
    script = [
        _call("write_file", {"file_path": "/skills/x.md", "content": "hi"}, "c1"),
        AIMessage(content="done"),
    ]
    agent = _agent([], script)
    out = await agent.ainvoke({"messages": [{"role": "user", "content": "write"}]}, _cfg("s"))
    tool_msgs = [m for m in out["messages"] if m.type == "tool"]
    assert "permission" in tool_msgs[0].content.lower()
