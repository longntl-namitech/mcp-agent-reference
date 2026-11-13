"""Async HTTP client for the CRM API with a uniform error shape."""

import json as jsonlib

import httpx

MAX_BODY = 4000


def is_error(obj) -> bool:
    return isinstance(obj, dict) and obj.get("error") is True


class ApiClient:
    def __init__(self, base_url: str, *, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=30)

    async def request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict | list:
        url = f"{self.base_url}{path}"
        try:
            resp = await self._client.request(
                method,
                url,
                json=json,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            return _error(None, method, url, f"{type(exc).__name__}: {exc}", None)
        if resp.status_code >= 400:
            return _error(resp.status_code, method, url, f"HTTP {resp.status_code}", _body(resp))
        if resp.status_code == 204 or not resp.content:
            return {"ok": True}
        return resp.json()


def _body(resp: httpx.Response):
    try:
        return resp.json()
    except (jsonlib.JSONDecodeError, UnicodeDecodeError):
        return resp.text[:MAX_BODY]


def _error(status, method, url, message, body) -> dict:
    return {
        "error": True,
        "statusCode": status,
        "method": method,
        "url": url,
        "message": message,
        "responseBody": body,
    }
