from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from .settings import Settings


@asynccontextmanager
async def open_mcp_tools(settings: Settings, user_token: str) -> AsyncIterator[list[BaseTool]]:
    """Open one gateway session for the request and yield its tools."""
    client = MultiServerMCPClient(
        {
            "gateway": {
                "transport": "http",
                "url": settings.gateway_url,
                "headers": {
                    "Authorization": f"Bearer {settings.gateway_secret}",
                    "access-token": user_token,
                },
            }
        }
    )
    async with client.session("gateway") as session:
        yield await load_mcp_tools(session)
