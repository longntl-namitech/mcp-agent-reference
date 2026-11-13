from fastapi import Header, HTTPException

DEMO_TOKENS: dict[str, str] = {
    "demo-token-alice": "alice",
    "demo-token-bob": "bob",
}


def require_user(authorization: str | None = Header(default=None)) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    user = DEMO_TOKENS.get(token) if scheme.lower() == "bearer" else None
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")
    return user
