import asyncio
import hashlib
from typing import Protocol

TENANT = "demo"


def user_id_for(token: str) -> str:
    """Stable id for a user token; the token itself is never stored."""
    return hashlib.sha256(token.encode()).hexdigest()[:16]


class Ownership(Protocol):
    async def claim(self, thread_id: str, user_id: str) -> bool:
        """True if the user owns the thread or has just claimed it."""


class MemoryOwnership:
    def __init__(self) -> None:
        self._owners: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def claim(self, thread_id: str, user_id: str) -> bool:
        async with self._lock:
            return self._owners.setdefault(thread_id, user_id) == user_id


class EsOwnership:
    def __init__(self, store) -> None:
        self._store = store

    async def claim(self, thread_id: str, user_id: str) -> bool:
        return await self._store.claim_session(thread_id, TENANT, user_id)
