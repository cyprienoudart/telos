"""
auth/handler.py — Authentication and session management for Project Telos.

Implements:
  - JWT access tokens (15-minute lifetime)
  - Refresh-token rotation with single-use token families (AUTH-112 fix)
  - Server-side revocation list in Redis
  - FastAPI middleware to validate bearer tokens on protected routes

Token family model (per AUTH-112):
  Each refresh token is part of a "family". When a refresh token is used:
    1. The old token is marked used in Redis.
    2. A new refresh token in the same family is issued.
    3. If an already-used token is presented again → the entire family is
       revoked (attacker detection).
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from typing import Any

import jwt
import redis.asyncio as aioredis
from fastapi import Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_ACCESS_TOKEN_TTL = 15 * 60          # 15 minutes in seconds
_REFRESH_TOKEN_TTL = 30 * 24 * 3600  # 30 days in seconds

_PUBLIC_ROUTES = {"/health", "/api/docs", "/metrics", "/api/v2/auth/login", "/api/v2/auth/refresh"}


class AuthHandler:
    def __init__(self, secret_key: str, redis_url: str) -> None:
        self._secret = secret_key
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    # ------------------------------------------------------------------
    # Access tokens (JWT)
    # ------------------------------------------------------------------

    def create_access_token(self, user_id: str, roles: list[str]) -> str:
        payload = {
            "sub": user_id,
            "roles": roles,
            "iat": int(time.time()),
            "exp": int(time.time()) + _ACCESS_TOKEN_TTL,
            "type": "access",
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def decode_access_token(self, token: str) -> dict[str, Any]:
        """Raises jwt.InvalidTokenError on failure."""
        return jwt.decode(token, self._secret, algorithms=["HS256"])

    # ------------------------------------------------------------------
    # Refresh tokens (opaque, stored in Redis)
    # ------------------------------------------------------------------

    async def create_refresh_token(self, user_id: str, family_id: str | None = None) -> tuple[str, str]:
        """
        Returns (token, family_id).
        Creates a new family if family_id is None.
        """
        if family_id is None:
            family_id = secrets.token_urlsafe(16)

        token = secrets.token_urlsafe(32)
        token_hash = _sha256(token)

        # Store: hash → {user_id, family_id, used: 0}
        key = f"rt:{token_hash}"
        await self._redis.hset(key, mapping={
            "user_id": user_id,
            "family_id": family_id,
            "used": "0",
        })
        await self._redis.expire(key, _REFRESH_TOKEN_TTL)

        return token, family_id

    async def rotate_refresh_token(self, old_token: str) -> tuple[str, str, str] | None:
        """
        Validate *old_token* and issue a new one.

        Returns (new_token, family_id, user_id) or None if invalid.
        If token reuse is detected, revokes the entire family.
        """
        token_hash = _sha256(old_token)
        key = f"rt:{token_hash}"

        data = await self._redis.hgetall(key)
        if not data:
            logger.warning("Refresh token not found (may be expired or invalid)")
            return None

        if data.get("used") == "1":
            # Reuse detected → revoke entire family
            family_id = data["family_id"]
            logger.warning("Refresh token reuse detected for family %s — revoking family", family_id)
            await self._revoke_family(data["user_id"], family_id)
            return None

        # Mark as used
        await self._redis.hset(key, "used", "1")

        user_id = data["user_id"]
        family_id = data["family_id"]

        # Check family revocation
        if await self._redis.sismember(f"rt:revoked_families:{user_id}", family_id):
            logger.warning("Token family %s is revoked", family_id)
            return None

        new_token, _ = await self.create_refresh_token(user_id, family_id)
        return new_token, family_id, user_id

    async def revoke_all_sessions(self, user_id: str) -> None:
        """Revoke all refresh tokens for a user (e.g., on password change)."""
        await self._redis.delete(f"rt:revoked_families:{user_id}")
        # Set a global revocation marker
        await self._redis.set(f"rt:all_revoked:{user_id}", "1", ex=_REFRESH_TOKEN_TTL)

    async def _revoke_family(self, user_id: str, family_id: str) -> None:
        await self._redis.sadd(f"rt:revoked_families:{user_id}", family_id)
        await self._redis.expire(f"rt:revoked_families:{user_id}", _REFRESH_TOKEN_TTL)


# ------------------------------------------------------------------
# Middleware
# ------------------------------------------------------------------

async def auth_middleware(request: Request, call_next: Any) -> Response:
    """FastAPI middleware: validate bearer JWT on protected routes."""
    if request.url.path in _PUBLIC_ROUTES or request.url.path.startswith("/health"):
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"error": "Missing or invalid Authorization header"}, status_code=401)

    token = auth_header.removeprefix("Bearer ").strip()
    handler: AuthHandler = request.app.state.auth

    try:
        payload = handler.decode_access_token(token)
        request.state.user_id = payload["sub"]
        request.state.roles = payload.get("roles", [])
    except jwt.ExpiredSignatureError:
        return JSONResponse({"error": "Token expired"}, status_code=401)
    except jwt.InvalidTokenError as exc:
        return JSONResponse({"error": f"Invalid token: {exc}"}, status_code=401)

    return await call_next(request)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
