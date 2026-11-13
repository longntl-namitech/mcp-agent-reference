"""Shared helpers for tool modules."""

from ..headers import user_token
from ..http import ApiClient, is_error

PAGE_MAX = 200


def clean(values: dict) -> dict:
    return {k: v for k, v in values.items() if v is not None}


async def call(
    api: ApiClient,
    method: str,
    path: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
) -> dict | list:
    """Call the API as the requesting user; return the error dict if no token was sent."""
    token = user_token()
    if isinstance(token, dict):
        return token
    return await api.request(
        method,
        path,
        token=token,
        json=clean(json) if json is not None else None,
        params=clean(params) if params is not None else None,
    )


async def fetch_all(api: ApiClient, path: str, params: dict | None = None) -> dict | list:
    """First page (up to the API maximum) of a collection, for filtering inside the gateway."""
    return await call(api, "GET", path, params={**(params or {}), "limit": PAGE_MAX})


__all__ = ["PAGE_MAX", "call", "clean", "fetch_all", "is_error"]
