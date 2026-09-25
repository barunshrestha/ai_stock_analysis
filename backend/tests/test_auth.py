"""Tests for Clerk session-token verification and route protection.

Tokens are signed with a throwaway RSA key; the JWKS lookup is patched to return its public half,
so no network or real Clerk tenant is needed. The DB is replaced by an in-memory fake.
"""

from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from backend import auth, config
from backend.deps import get_db
from backend.main import app

pytestmark = pytest.mark.real_auth

ISSUER = "https://test-app.clerk.accounts.dev"
FRONTEND_ORIGIN = "http://localhost:3003"
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeUserDb:
    def __init__(self):
        self.users: dict[str, dict] = {}

    def upsert_user(self, user_id, email, make_admin=False):
        user = self.users.setdefault(user_id, {"id": user_id, "email": email, "role": "user"})
        if make_admin:
            user["role"] = "admin"
        return dict(user)

    def admin_remove_stock_from_industry(self, symbol, industry):
        return False, "Assignment not found"


def make_token(key=_PRIVATE_KEY, **overrides) -> str:
    now = int(time.time())
    claims = {
        "sub": "user_abc",
        "iss": ISSUER,
        "azp": FRONTEND_ORIGIN,
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "email": "someone@example.com",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256")


@pytest.fixture(autouse=True)
def clerk_config(monkeypatch):
    monkeypatch.setattr(config, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(config, "CLERK_JWKS_URL", f"{ISSUER}/.well-known/jwks.json")
    monkeypatch.setattr(config, "CLERK_AUTHORIZED_PARTIES", [FRONTEND_ORIGIN])
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"admin@example.com"})
    monkeypatch.setattr(auth, "_signing_key", lambda token: _PRIVATE_KEY.public_key())


@pytest.fixture
def client():
    fake_db = FakeUserDb()
    app.dependency_overrides[get_db] = lambda: fake_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestVerifySessionToken:
    def test_valid_token_returns_claims(self):
        assert auth.verify_session_token(make_token())["sub"] == "user_abc"

    def test_expired_token_rejected(self):
        past = int(time.time()) - 3600
        with pytest.raises(jwt.ExpiredSignatureError):
            auth.verify_session_token(make_token(iat=past - 60, nbf=past - 60, exp=past))

    def test_wrong_issuer_rejected(self):
        with pytest.raises(jwt.InvalidIssuerError):
            auth.verify_session_token(make_token(iss="https://evil.example.com"))

    def test_unknown_authorized_party_rejected(self):
        with pytest.raises(jwt.InvalidTokenError):
            auth.verify_session_token(make_token(azp="https://evil.example.com"))

    def test_signature_from_other_key_rejected(self):
        with pytest.raises(jwt.InvalidSignatureError):
            auth.verify_session_token(make_token(key=_OTHER_PRIVATE_KEY))

    def test_missing_subject_rejected(self):
        with pytest.raises(jwt.MissingRequiredClaimError):
            auth.verify_session_token(make_token(sub=None))

    def test_unconfigured_issuer_raises(self, monkeypatch):
        monkeypatch.setattr(config, "CLERK_ISSUER", "")
        with pytest.raises(auth.AuthNotConfiguredError):
            auth.verify_session_token(make_token())


class TestProtectedRoutes:
    def test_missing_header_is_401(self, client):
        res = client.get("/api/options/strategies")
        assert res.status_code == 401
        assert res.headers["www-authenticate"] == "Bearer"

    def test_invalid_token_is_401(self, client):
        assert client.get("/api/options/strategies", headers=bearer("not-a-jwt")).status_code == 401

    def test_valid_token_is_200(self, client):
        assert client.get("/api/options/strategies", headers=bearer(make_token())).status_code == 200

    @pytest.mark.parametrize(
        "method,path",
        [
            ("get", "/api/portfolio/portfolios"),
            ("get", "/api/options/trades"),
            ("get", "/api/news/portfolio"),
            ("get", "/api/automation/AAPL"),
            ("post", "/api/dca/backtest"),
            ("post", "/api/ai/moat"),
            ("get", "/api/admin/industries"),
        ],
    )
    def test_private_routes_require_token(self, client, method, path):
        assert getattr(client, method)(path).status_code == 401

    def test_unconfigured_server_is_503(self, client, monkeypatch):
        monkeypatch.setattr(config, "CLERK_ISSUER", "")
        assert client.get("/api/options/strategies", headers=bearer(make_token())).status_code == 503


class TestAdminRole:
    def test_non_admin_gets_403_on_changes(self, client):
        res = client.post(
            "/api/admin/industries/assign",
            json={"symbol": "AAPL", "industries": ["Tech"]},
            headers=bearer(make_token()),
        )
        assert res.status_code == 403

    def test_admin_email_passes_role_check(self, client):
        token = make_token(sub="user_admin", email="Admin@Example.com")
        res = client.delete("/api/admin/industries/stock/ZZZZ/Nope", headers=bearer(token))
        # 404 comes from the handler, so the admin gate was passed.
        assert res.status_code == 404


class TestPublicRoutes:
    def test_health_is_public(self, client):
        assert client.get("/api/health").status_code == 200

    def test_cached_ai_read_is_public(self, client, monkeypatch):
        class CacheDb:
            def get_ai_analysis_cache(self, ticker, analysis_type):
                return None

        app.dependency_overrides[get_db] = lambda: CacheDb()
        res = client.get("/api/ai/moat/AAPL")
        assert res.status_code == 200
        assert res.json()["cached"] is False
