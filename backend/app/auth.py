"""
Supabase JWT verification for FastAPI (ES256 via JWKS).

Uses SUPABASE_JWKS_URL to fetch public keys and verify tokens.
No shared secret needed.

Env vars required:
  SUPABASE_JWKS_URL  – https://<project>.supabase.co/auth/v1/.well-known/jwks.json
  SUPABASE_ISSUER    – https://<project>.supabase.co/auth/v1
  SUPABASE_AUDIENCE  – authenticated
"""

from __future__ import annotations

import logging, os
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

logger = logging.getLogger("labellens.auth")

# Lazily initialised PyJWKClient keyed by URL (survives hot-reloads)
_jwks_client = None
_jwks_client_url = None


def _get_jwks_client():
    global _jwks_client, _jwks_client_url
    jwks_url = os.getenv("SUPABASE_JWKS_URL", "")
    if not jwks_url:
        raise HTTPException(503, "Auth not configured (SUPABASE_JWKS_URL missing)")
    # Re-create client if URL changed (e.g. after env reload)
    if _jwks_client is None or _jwks_client_url != jwks_url:
        try:
            from jwt import PyJWKClient
        except ImportError as exc:
            raise HTTPException(500, f"Missing dependency: {exc}")
        logger.info("Initializing JWKS client for: %s", jwks_url)
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
        _jwks_client_url = jwks_url
    return _jwks_client


def _verify_supabase_jwt(token: str) -> Dict[str, Any]:
    try:
        import jwt as pyjwt
    except ImportError as exc:
        raise HTTPException(500, f"Missing dependency: {exc}")

    jwks_url = os.getenv("SUPABASE_JWKS_URL", "")
    if not jwks_url:
        raise HTTPException(503, "Auth not configured (SUPABASE_JWKS_URL missing)")

    issuer = os.getenv("SUPABASE_ISSUER", "")
    audience = os.getenv("SUPABASE_AUDIENCE", "authenticated")

    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)

        payload = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience=audience if audience else None,
            issuer=issuer if issuer else None,
            options={
                "verify_aud": bool(audience),
                "verify_iss": bool(issuer),
            },
        )
        return payload

    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(401, f"Invalid token: {exc}")
    except Exception as exc:
        logger.error("JWKS verification error: %s", exc)
        raise HTTPException(401, f"Token verification failed: {exc}")


class AuthUser:
    def __init__(self, user_id: str, email: Optional[str] = None):
        self.user_id = user_id
        self.email = email

    @property
    def sub(self) -> str:
        return self.user_id


def get_current_user(request: Request) -> AuthUser:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")

    token = auth_header[7:]
    claims = _verify_supabase_jwt(token)

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(401, "Token missing 'sub' claim")

    return AuthUser(
        user_id=user_id,
        email=claims.get("email"),
    )


def get_optional_user(request: Request) -> Optional[AuthUser]:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        return get_current_user(request)
    except HTTPException:
        return None
