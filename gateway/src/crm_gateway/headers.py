"""Per-request user identity forwarded by the agent."""

from fastmcp.server.dependencies import get_http_headers


def user_token() -> str | dict:
    token = get_http_headers().get("access-token")
    if token:
        return token
    return {
        "error": True,
        "statusCode": None,
        "method": None,
        "url": None,
        "message": "missing access-token header",
        "responseBody": None,
    }
