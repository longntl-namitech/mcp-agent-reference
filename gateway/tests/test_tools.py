import asyncio
import re
import socket

import httpx
import pytest
import uvicorn
from crm_gateway import WRITE_ACTIONS
from crm_gateway.server import create_gateway
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mock_crm.app import create_app

SECRET = "s3cret-x"
ALICE = "demo-token-alice"
NAME_RE = re.compile(r"^(contacts|companies|deals|tasks|notes|reports)_[a-z_]+$")


async def serve(gateway):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    config = uvicorn.Config(
        gateway.http_app(), host="127.0.0.1", port=port, log_level="warning", lifespan="on"
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    return f"http://127.0.0.1:{port}", server, task


def connect(base: str, token: str | None = ALICE) -> Client:
    headers = {"Authorization": f"Bearer {SECRET}"}
    if token:
        headers["access-token"] = token
    return Client(StreamableHttpTransport(f"{base}/mcp", headers=headers))


@pytest.fixture
async def base(tmp_path):
    app = create_app(str(tmp_path / "crm.db"))
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://crm.test")
    gateway = create_gateway("http://crm.test", SECRET, http_client=http)
    url, server, task = await serve(gateway)
    yield url
    server.should_exit = True
    await task


async def test_tool_count(base):
    async with connect(base) as client:
        names = [t.name for t in await client.list_tools()]
    assert 55 <= len(names) <= 65
    assert all(NAME_RE.match(n) for n in names), names


async def test_every_tool_has_docstring(base):
    async with connect(base) as client:
        tools = await client.list_tools()
    short = [t.name for t in tools if len(t.description or "") < 20]
    assert not short


async def test_list_deals(base):
    async with connect(base) as client:
        result = await client.call_tool("deals_list", {"limit": 3})
    assert len(result.data) == 3
    assert {"id", "title", "stage"} <= set(result.data[0])


async def test_move_stage_roundtrip(base):
    async with connect(base) as client:
        moved = await client.call_tool("deals_move_stage", {"id": 1, "stage": "won"})
        assert moved.data["stage"] == "won"
        got = await client.call_tool("deals_get", {"id": 1})
        assert got.data["stage"] == "won"
        won = await client.call_tool("deals_list_by_stage", {"stage": "won"})
        assert 1 in [d["id"] for d in won.data]


async def test_unknown_id_structured(base):
    async with connect(base) as client:
        result = await client.call_tool("deals_get", {"id": 9999})
    assert result.data["error"] is True
    assert result.data["statusCode"] == 404


async def test_missing_access_token(base):
    async with connect(base, token=None) as client:
        result = await client.call_tool("deals_list", {})
    assert result.data["message"] == "missing access-token header"


async def test_bad_user_token_is_401(base):
    async with connect(base, token="nope") as client:
        result = await client.call_tool("deals_list", {})
    assert result.data["statusCode"] == 401


async def test_reports_and_domain_tools(base):
    async with connect(base) as client:
        pipeline = (await client.call_tool("reports_pipeline_by_stage", {})).data
        assert [r["stage"] for r in pipeline] == ["lead", "qualified", "proposal", "won", "lost"]
        assert sum(r["count"] for r in pipeline) > 0
        overdue = await client.call_tool("reports_overdue_tasks", {"today": "2999-01-01"})
        assert all(not t["done"] for t in overdue.data)
        task = (await client.call_tool("tasks_create", {"title": "Call back"})).data
        done = await client.call_tool("tasks_complete", {"id": task["id"]})
        assert done.data["done"] is True
        merged = await client.call_tool("contacts_merge", {"keep_id": 1, "merge_id": 2})
        assert merged.data["id"] == 1


SAMPLE = {"integer": 1, "number": 1, "boolean": True, "string": "x"}


def sample_args(schema: dict) -> dict:
    args = {}
    for name in schema.get("required", []):
        prop = schema["properties"][name]
        args[name] = prop["enum"][0] if "enum" in prop else SAMPLE[prop["type"]]
    return args


async def test_write_actions_cover_writes():
    """Every tool that issues POST/PATCH/DELETE has a write action, and only those."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        return httpx.Response(200, json=[])

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = create_gateway("http://api.test", SECRET, http_client=http)
    url, server, task = await serve(gateway)
    try:
        async with connect(url) as client:
            tools = await client.list_tools()
            for tool in tools:
                seen.clear()
                await client.call_tool(tool.name, sample_args(tool.inputSchema))
                assert seen, f"{tool.name} made no API call"
                action = tool.name.split("_")[1]
                writes = any(m in ("POST", "PATCH", "DELETE") for m in seen)
                assert writes == (action in WRITE_ACTIONS), tool.name
    finally:
        server.should_exit = True
        await task
