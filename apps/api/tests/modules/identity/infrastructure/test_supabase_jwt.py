from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.modules.identity.domain.errors import InvalidAccessToken
from app.modules.identity.infrastructure.supabase_jwt import SupabaseJwtVerifier
from app.shared.config import Settings


class FakeSigningKey:
    def __init__(self, key: object) -> None:
        self.key = key


class FakeJwks:
    def __init__(self, public_key: object) -> None:
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
        assert token
        return FakeSigningKey(self.public_key)


def settings() -> Settings:
    return Settings(
        app_env="test",
        auth_mode="fixture",
        database_url="sqlite+aiosqlite:///:memory:",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
    )


def sign_token(private_key: object, kid: str, claims: dict[str, object]) -> str:
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": kid})


def valid_claims() -> dict[str, object]:
    return {
        "sub": str(uuid4()),
        "email": "manager@example.test",
        "aud": "authenticated",
        "iss": "https://lgjohsxipfctgooiuqnv.supabase.co/auth/v1",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }


def signed_token_with_invalid_claim(claim: str, ec_key_pair) -> str:
    claims = valid_claims()
    replacements: dict[str, object] = {
        "aud": "wrong-audience",
        "iss": "https://issuer.invalid",
        "exp": datetime.now(UTC) - timedelta(minutes=1),
    }
    claims[claim] = replacements[claim]
    return sign_token(ec_key_pair.private, "test-key", claims)


def test_supabase_verifier_accepts_expected_es256_claims(ec_key_pair) -> None:
    expected_user_id = uuid4()
    token = sign_token(
        ec_key_pair.private,
        kid="test-key",
        claims={**valid_claims(), "sub": str(expected_user_id)},
    )
    verifier = SupabaseJwtVerifier(settings(), jwks_client=FakeJwks(ec_key_pair.public))

    principal = verifier.verify(token)

    assert principal.user_id == expected_user_id
    assert principal.email == "manager@example.test"


@pytest.mark.parametrize("claim", ["aud", "iss", "exp"])
def test_supabase_verifier_rejects_invalid_required_claim(claim, ec_key_pair) -> None:
    token = signed_token_with_invalid_claim(claim, ec_key_pair)
    verifier = SupabaseJwtVerifier(settings(), jwks_client=FakeJwks(ec_key_pair.public))

    with pytest.raises(InvalidAccessToken):
        verifier.verify(token)


@pytest.mark.parametrize("claim", ["sub", "email", "aud", "iss", "exp"])
def test_supabase_verifier_rejects_missing_required_claim(claim, ec_key_pair) -> None:
    claims = valid_claims()
    del claims[claim]
    token = sign_token(ec_key_pair.private, "test-key", claims)
    verifier = SupabaseJwtVerifier(settings(), jwks_client=FakeJwks(ec_key_pair.public))

    with pytest.raises(InvalidAccessToken):
        verifier.verify(token)


def test_supabase_verifier_rejects_signature_from_other_key(ec_key_pair) -> None:
    other_private = ec.generate_private_key(ec.SECP256R1())
    token = sign_token(other_private, "test-key", valid_claims())
    verifier = SupabaseJwtVerifier(settings(), jwks_client=FakeJwks(ec_key_pair.public))

    with pytest.raises(InvalidAccessToken):
        verifier.verify(token)


def test_supabase_verifier_rejects_non_es256_algorithm(ec_key_pair) -> None:
    token = jwt.encode(
        valid_claims(),
        "fixture-secret-with-no-production-value",
        algorithm="HS256",
        headers={"kid": "test-key"},
    )
    verifier = SupabaseJwtVerifier(settings(), jwks_client=FakeJwks(ec_key_pair.public))

    with pytest.raises(InvalidAccessToken):
        verifier.verify(token)


@pytest.mark.parametrize(
    ("claim", "value"),
    [("sub", "not-a-uuid"), ("email", 123)],
)
def test_supabase_verifier_rejects_invalid_identity_claim(
    claim: str,
    value: object,
    ec_key_pair,
) -> None:
    claims = valid_claims()
    claims[claim] = value
    token = sign_token(ec_key_pair.private, "test-key", claims)
    verifier = SupabaseJwtVerifier(settings(), jwks_client=FakeJwks(ec_key_pair.public))

    with pytest.raises(InvalidAccessToken):
        verifier.verify(token)
