import asyncio
import json
import socket

import httpx
import uvicorn
from crm_agent.app import create_app as create_agent_app
from crm_agent.settings import Settings
from crm_gateway.server import create_gateway
from fakes import ScriptedChatModel
from langchain_core.messages import AIMessage
from mock_crm.app import create_app as create_mock_api

SECRET = "e2e-secret"
ALICE = {"Authorization": "Bearer demo-token-alice"}


async def serve(app):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    )
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    return f"http://127.0.0.1:{port}", server, task


def _call(name, args, id_):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id_}])


async def test_approve_moves_deal_stage(tmp_path):
    api_url, api_server, api_task = await serve(create_mock_api(str(tmp_path / "crm.db")))
    gw_url, gw_server, gw_task = await serve(create_gateway(api_url, SECRET).http_app())
    try:
        script = [
            _call("search_tools", {"query": "move deal stage"}, "c1"),
            _call("deals_move_stage", {"id": 1, "stage": "won"}, "c2"),
            AIMessage(content="Moved."),
        ]
        settings = Settings(gateway_url=f"{gw_url}/mcp", gateway_secret=SECRET)
        agent = create_agent_app(settings, model=ScriptedChatModel(script=script))
        agent_client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=agent), base_url="http://agent", timeout=60
        )
        async with httpx.AsyncClient(base_url=api_url, headers=ALICE) as api:
            before = (await api.get("/deals/1")).json()["stage"]
            assert before != "won"

            body = {"thread_id": "e2e", "message": "Move deal 1 to won"}
            first = await agent_client.post("/chat/stream", json=body, headers=ALICE)
            lines = [json.loads(x) for x in first.text.splitlines() if x]
            assert lines[-1]["type"] == "interrupt"
            assert json.loads(lines[-1]["content"])[0]["name"] == "deals_move_stage"
            assert (await api.get("/deals/1")).json()["stage"] == before

            body = {"thread_id": "e2e", "resume": {"decision": "approve"}}
            second = await agent_client.post("/chat/stream", json=body, headers=ALICE)
            lines = [json.loads(x) for x in second.text.splitlines() if x]
            assert "interrupt" not in {x["type"] for x in lines}
            assert (await api.get("/deals/1")).json()["stage"] == "won"
    finally:
        for server in (gw_server, api_server):
            server.should_exit = True
        await asyncio.gather(gw_task, api_task)
