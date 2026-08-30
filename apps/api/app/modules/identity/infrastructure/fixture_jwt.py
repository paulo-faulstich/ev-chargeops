from uuid import UUID

from app.modules.identity.domain.auth import AuthPrincipal
from app.modules.identity.domain.errors import InvalidAccessToken
from app.shared.config import Settings

FIXTURE_AUTH_USER_ID = UUID("50000000-0000-0000-0000-000000000001")
FIXTURE_EMAIL = "manager@example.test"


class FixtureTokenVerifier:
    def __init__(self, settings: Settings) -> None:
        self.expected_token = settings.fixture_auth_token
        self.email = settings.demo_manager_email or FIXTURE_EMAIL

    def verify(self, token: str) -> AuthPrincipal:
        if token != self.expected_token:
            raise InvalidAccessToken
        return AuthPrincipal(user_id=FIXTURE_AUTH_USER_ID, email=self.email)
