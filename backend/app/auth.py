"""
Supabase JWT verification for FastAPI (HS256).

Uses SUPABASE_JWT_SECRET (from Supabase Project Settings -> API -> JWT Secret).
No JWKS fetch needed.

Env vars required:
  SUPABASE_JWT_SECRET – Supabase JWT secret
  SUPABASE_ISSUER     – https://<project>.supabase.co/auth/v1
  SUPABASE_AUDIENCE   – authenticated
"""

from __future__ import annotations

import logging, os
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

logger = logging.getLogger("labellens.auth")

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SUPABASE_ISSUER = os.getenv("SUPABASE_ISSUER", "")
SUPABASE_AUDIENCE = os.getenv("SUPABASE_AUDIENCE", "authenticated")


def _verify_supabase_jwt(token: str) -> Dict[str, Any]:
    try:
        import jwt as pyjwt
    except ImportError as exc:
        raise HTTPException(500, f"Missing dependency: {exc}")

    if not SUPABASE_JWT_SECRET:
        raise HTTPException(503, "Auth not configured (SUPABASE_JWT_SECRET missing)")

    try:
        payload = pyjwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience=SUPABASE_AUDIENCE if SUPABASE_AUDIENCE else None,
            issuer=SUPABASE_ISSUER if SUPABASE_ISSUER else None,
            options={
                "verify_aud": bool(SUPABASE_AUDIENCE),
                "verify_iss": bool(SUPABASE_ISSUER),
            },
        )
        return payload

    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(401, f"Invalid token: {exc}")


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