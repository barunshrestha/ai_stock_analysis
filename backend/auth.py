"""Authentication: verify Clerk session JWTs and resolve the current app user.

Usage in a router:

    from backend.auth import CurrentUser, get_current_user

    @router.get("/things")
    def list_things(user: CurrentUser = Depends(get_current_user), db=Depends(get_db)):
        return db.list_things(user.id)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientError

from backend import config
from backend.deps import get_db

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)
_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}
# Tolerate small clock drift between Clerk and this server.
_CLOCK_LEEWAY_SECONDS = 10


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class AuthNotConfiguredError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    # Keys are cached in-process; PyJWKClient refetches when it sees an unknown `kid` (key rotation).
    return PyJWKClient(config.CLERK_JWKS_URL, cache_keys=True, lifespan=3600)


def _signing_key(token: str):
    return _jwks_client().get_signing_key_from_jwt(token).key


def verify_session_token(token: str) -> dict:
    """Return verified claims or raise jwt.InvalidTokenError / AuthNotConfiguredError."""
    if not config.CLERK_ISSUER or not config.CLERK_JWKS_URL:
        raise AuthNotConfiguredError("CLERK_ISSUER is not set")

    claims = jwt.decode(
        token,
        _signing_key(token),
        algorithms=["RS256"],
        issuer=config.CLERK_ISSUER,
        leeway=_CLOCK_LEEWAY_SECONDS,
        # Clerk session tokens carry no `aud`; origin binding is enforced through `azp` below.
        options={"require": ["exp", "iat", "iss", "sub"], "verify_aud": False},
    )
    authorized_party = claims.get("azp")
    if authorized_party and authorized_party not in config.CLERK_AUTHORIZED_PARTIES:
        raise jwt.InvalidTokenError("Token was issued for an unrecognized origin")
    return claims


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db=Depends(get_db),
) -> CurrentUser:
    """FastAPI dependency: 401 unless the request carries a valid Clerk session token."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Sign in required.", headers=_UNAUTHORIZED_HEADERS)

    try:
        claims = verify_session_token(credentials.credentials)
    except AuthNotConfiguredError:
        logger.error("Auth request rejected: CLERK_ISSUER is not configured")
        raise HTTPException(status_code=503, detail="Authentication is not configured on the server.")
    except PyJWKClientError as exc:
        logger.warning("Could not load Clerk signing keys: %s", exc)
        raise HTTPException(status_code=503, detail="Authentication service unavailable. Try again shortly.")
    except jwt.InvalidTokenError as exc:
        logger.info("Rejected session token: %s", exc)
        raise HTTPException(
            status_code=401, detail="Your session is invalid or expired. Sign in again.",
            headers=_UNAUTHORIZED_HEADERS,
        )

    email = claims.get("email") or None
    make_admin = bool(email) and email.lower() in config.ADMIN_EMAILS
    record = db.upsert_user(claims["sub"], email, make_admin=make_admin)
    return CurrentUser(id=record["id"], email=record["email"], role=record["role"])


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """FastAPI dependency: 403 unless the signed-in user is an admin."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user
