from typing import Any, Protocol
from uuid import UUID

import jwt
from jwt import PyJWKClient

from app.modules.identity.domain.auth import AuthPrincipal
from app.modules.identity.domain.errors import InvalidAccessToken
from app.shared.config import Settings


class SigningKey(Protocol):
    key: Any


class JwksClient(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> SigningKey: ...


class SupabaseJwtVerifier:
    def __init__(
        self,
        settings: Settings,
        jwks_client: JwksClient | None = None,
    ) -> None:
        self.settings = settings
        self.jwks: JwksClient = jwks_client or PyJWKClient(
            settings.supabase_jwks_url,
            cache_keys=True,
        )

    def verify(self, token: str) -> AuthPrincipal:
        try:
            signing_key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256"],
                audience=self.settings.supabase_jwt_audience,
                issuer=self.settings.supabase_issuer,
                options={"require": ["sub", "email", "aud", "iss", "exp"]},
            )
            subject = claims["sub"]
            email = claims["email"]
            if not isinstance(subject, str) or not isinstance(email, str) or not email:
                raise ValueError("invalid identity claim")
            return AuthPrincipal(user_id=UUID(subject), email=email)
        except (jwt.PyJWTError, ValueError, KeyError, TypeError) as error:
            raise InvalidAccessToken from error
