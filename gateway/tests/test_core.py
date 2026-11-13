import asyncio
import logging
import socket

import httpx
import pytest
import uvicorn
from crm_gateway.auth import SharedSecretVerifier
from crm_gateway.headers import user_token
from crm_gateway.http import ApiClient, is_error
from crm_gateway.server import create_gateway
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mock_crm.app import create_app

ERROR_KEYS = {"error", "statusCode", "method", "url", "message", "responseBody"}


def api(handler) -> ApiClient:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ApiClient("http://api.test", client=client)


async def test_success_json():
    def handler(request):
        assert request.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, json={"id": 1})

    assert await api(handler).request("GET", "/contacts/1", token="tok") == {"id": 1}


async def test_204_ok():
    result = await api(lambda r: httpx.Response(204)).request("DELETE", "/contacts/1", token="t")
    assert result == {"ok": True}


async def test_http_error_shape():
    result = await api(lambda r: httpx.Response(401, json={"detail": "bad"})).request(
        "GET", "/contacts", token="t"
    )
    assert is_error(result)
    assert set(result) == ERROR_KEYS
    assert result["statusCode"] == 401
    assert result["method"] == "GET"
    assert result["responseBody"] == {"detail": "bad"}


async def test_text_body_truncated():
    result = await api(lambda r: httpx.Response(500, text="x" * 5000)).request(
        "GET", "/contacts", token="t"
    )
    assert len(result["responseBody"]) == 4000


async def test_network_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    result = await api(handler).request("GET", "/contacts", token="t")
    assert result["error"] is True
    assert result["statusCode"] is None


def test_is_error():
    assert is_error({"error": True})
    assert not is_error({"id": 1})
    assert not is_error([{"error": True}])


async def test_verifier():
    verifier = SharedSecretVerifier("s3cret-x")
    assert await verifier.verify_token("s3cret-x") is not None
    assert await verifier.verify_token("wrong") is None


def add_probe_tool(gateway, calls):
    @gateway.tool
    async def probe() -> dict:
        """Call the API with the caller's token."""
        token = user_token()
        if isinstance(token, dict):
            return token
        result = await gateway.api.request("GET", "/ping", token=token)
        calls.append(result)
        return result if isinstance(result, dict) else {"items": result}

    return probe


SEEN: list[str] = []


def _record(request):
    SEEN.append(request.headers["authorization"])
    return httpx.Response(200, json={"ok": True})


gateway_api = api(_record)


@pytest.fixture
async def http_gateway():
    """Gateway served over real streamable HTTP on a free port."""
    calls: list = []
    SEEN.clear()
    gateway = create_gateway("http://api.test", "s3cret-x", http_client=gateway_api._client)
    add_probe_tool(gateway, calls)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    config = uvicorn.Config(
        gateway.http_app(), host="127.0.0.1", port=port, log_level="debug", lifespan="on"
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    yield f"http://127.0.0.1:{port}", calls
    server.should_exit = True
    await task


def http_client(base: str, secret: str, token: str | None = None) -> Client:
    headers = {"Authorization": f"Bearer {secret}"}
    if token:
        headers["access-token"] = token
    return Client(StreamableHttpTransport(f"{base}/mcp", headers=headers))


async def test_health(http_gateway):
    base, _ = http_gateway
    async with httpx.AsyncClient() as client:
        assert (await client.get(f"{base}/health")).status_code == 200


async def test_secret_required(http_gateway):
    base, _ = http_gateway
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{base}/mcp", json={})
        assert resp.status_code == 401
        resp = await client.post(f"{base}/mcp", json={}, headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401


async def test_token_reaches_api(http_gateway):
    base, calls = http_gateway
    async with http_client(base, "s3cret-x", "tok-y") as client:
        result = await client.call_tool("probe", {})
    assert result.data == {"ok": True}
    assert SEEN == ["Bearer tok-y"]


async def test_missing_access_token(http_gateway):
    base, _ = http_gateway
    async with http_client(base, "s3cret-x") as client:
        result = await client.call_tool("probe", {})
    assert result.data["message"] == "missing access-token header"
    assert result.data["statusCode"] is None


async def test_user_token_without_request():
    assert user_token()["message"] == "missing access-token header"


async def test_against_mock_api(tmp_path):
    app = create_app(str(tmp_path / "crm.db"))
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://crm.test")
    result = await ApiClient("http://crm.test", client=http).request(
        "GET", "/contacts", token="demo-token-alice", params={"limit": 1}
    )
    assert not is_error(result)
    bad = await ApiClient("http://crm.test", client=http).request("GET", "/contacts", token="nope")
    assert bad["statusCode"] == 401


async def test_no_secrets_in_logs(http_gateway, caplog):
    base, _ = http_gateway
    with caplog.at_level(logging.DEBUG):
        async with http_client(base, "s3cret-x", "tok-y") as client:
            await client.call_tool("probe", {})
    assert "probe" in caplog.text  # middleware logged something
    assert "s3cret-x" not in caplog.text
    assert "tok-y" not in caplog.text
