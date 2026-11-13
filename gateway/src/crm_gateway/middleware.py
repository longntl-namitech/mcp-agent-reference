"""Logs tool name, duration and outcome only - never arguments, results or headers."""

import logging
import time

from fastmcp.server.middleware import Middleware

log = logging.getLogger("crm_gateway")


class ToolLogMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        start = time.perf_counter()
        status = "error"
        try:
            result = await call_next(context)
            status = "ok"
            return result
        finally:
            ms = (time.perf_counter() - start) * 1000
            log.info("tool=%s duration_ms=%.1f status=%s", context.message.name, ms, status)
