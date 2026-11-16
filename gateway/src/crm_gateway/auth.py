"""Bearer shared-secret verification for the gateway."""

import hmac

from fastmcp.server.auth import AccessToken, TokenVerifier


class SharedSecretVerifier(TokenVerifier):
    def __init__(self, secret: str):
        super().__init__()
        self._secret = secret.encode()

    async def verify_token(self, token: str) -> AccessToken | None:
        if hmac.compare_digest(token.encode(), self._secret):
            return AccessToken(token="gateway", client_id="gateway", scopes=[])
        return None
