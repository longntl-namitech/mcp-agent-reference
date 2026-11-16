import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import pytest
from crm_agent.app import create_app
from crm_agent.settings import Settings
from fakes import ScriptedChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

ALICE = {"Authorization": "Bearer demo-token-alice"}
BOB = {"Authorization": "Bearer demo-token-bob"}


def _call(name, args, id_):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id_}])


def _write_script():
    return [
        _call("search_tools", {"query": "update deal"}, "c1"),
        _call("deals_update", {"deal_id": "d1", "title": "x"}, "c2"),
        AIMessage(content="done"),
    ]


class Harness:
    def __init__(self, script, opener_error=None):
        self.calls = []
        self.opened = 0
        self.opener_error = opener_error
        self.model = ScriptedChatModel(script=script)

    def _tools(self):
        def deals_update(deal_id: str, title: str) -> str:
            """Update a deal title."""
            self.calls.append(deal_id)
            return "updated"

        return [StructuredTool.from_function(deals_update)]

    @asynccontextmanager
    async def opener(self, settings, token):
        self.opened += 1
        if self.opener_error:
            raise self.opener_error
        yield self._tools()

    def client(self):
        app = create_app(Settings(gateway_secret="s"), model=self.model, tools_opener=self.opener)
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def _chat(client, headers, **body):
    resp = await client.post("/chat/stream", json=body, headers=headers)
    lines = [json.loads(x) for x in resp.text.splitlines() if x] if resp.status_code == 200 else []
    return resp, lines


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Basic x"}])
async def test_requires_auth(headers):
    h = Harness([])
    async with h.client() as c:
        resp, _ = await _chat(c, headers, thread_id="t", message="hi")
    assert resp.status_code == 401
    assert h.opened == 0


@pytest.mark.parametrize(
    "resume, ran",
    [({"decision": "approve"}, 1), ({"decision": "reject", "message": "no"}, 0)],
    ids=["approve", "reject"],
)
async def test_interrupt_then_resume(resume, ran):
    h = Harness(_write_script())
    async with h.client() as c:
        resp, lines = await _chat(c, ALICE, thread_id="t", message="rename d1")
        assert resp.status_code == 200
        assert resp.headers["x-accel-buffering"] == "no"
        assert lines[-1]["type"] == "interrupt"
        assert json.loads(lines[-1]["content"])[0]["name"] == "deals_update"
        assert h.calls == []
        resp, lines = await _chat(c, ALICE, thread_id="t", resume=resume)
        assert resp.status_code == 200
        assert "interrupt" not in {x["type"] for x in lines}
        assert len(h.calls) == ran
        assert "done" in "".join(x["content"] for x in lines if x["type"] == "token")


async def test_resume_without_pending_409():
    h = Harness([AIMessage(content="hi")])
    async with h.client() as c:
        await _chat(c, ALICE, thread_id="t", message="hello")
        resp, _ = await _chat(c, ALICE, thread_id="t", resume={"decision": "approve"})
    assert resp.status_code == 409


async def test_message_while_pending_409():
    h = Harness(_write_script())
    async with h.client() as c:
        await _chat(c, ALICE, thread_id="t", message="rename d1")
        resp, _ = await _chat(c, ALICE, thread_id="t", message="again")
    assert resp.status_code == 409


async def test_gateway_down_error_event():
    h = Harness([], opener_error=ConnectionError("gateway unreachable"))
    async with h.client() as c:
        resp, lines = await _chat(c, ALICE, thread_id="t", message="hi")
    assert [x["type"] for x in lines] == ["start", "error"]
    assert "gateway unreachable" in lines[1]["content"]


async def test_other_user_403():
    h = Harness([AIMessage(content="hi")])
    async with h.client() as c:
        await _chat(c, ALICE, thread_id="t", message="hello")
        resp, _ = await _chat(c, BOB, thread_id="t", message="hello")
    assert resp.status_code == 403


async def test_concurrent_first_claim():
    h = Harness([AIMessage(content="hi")])
    async with h.client() as c:
        a, b = await asyncio.gather(
            _chat(c, ALICE, thread_id="new", message="x"),
            _chat(c, BOB, thread_id="new", message="x"),
        )
    assert sorted([a[0].status_code, b[0].status_code]) == [200, 403]


async def test_health_and_index():
    h = Harness([])
    async with h.client() as c:
        assert (await c.get("/health")).json() == {"status": "ok"}
        assert (await c.get("/")).status_code == 200
