"""Gateway factory."""

import httpx
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .auth import SharedSecretVerifier
from .http import ApiClient
from .middleware import ToolLogMiddleware


def create_gateway(
    api_base_url: str, secret: str, *, http_client: httpx.AsyncClient | None = None
) -> FastMCP:
    gateway = FastMCP("crm-gateway", auth=SharedSecretVerifier(secret))
    gateway.add_middleware(ToolLogMiddleware())
    gateway.api = ApiClient(api_base_url, client=http_client)  # type: ignore[attr-defined]

    @gateway.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    return gateway
