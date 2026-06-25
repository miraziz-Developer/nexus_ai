"""Sign In with Chutes — OAuth mock + session management."""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, status

from app.core.chutes_client import ChutesClientError, get_chutes_client
from app.core.config import get_settings
from app.core.database import sessions_db, users_db
from app.models.schemas import (
    AuthResponse,
    OAuthCallbackRequest,
    SignInRequest,
    UserRole,
    UserSchema,
)

logger = logging.getLogger("aether.api.auth")
router = APIRouter(prefix="/auth", tags=["Authentication"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _create_session(chutes_id: str) -> str:
    token = secrets.token_urlsafe(32)
    sessions_db[token] = {
        "chutes_id": chutes_id,
        "created_at": _utcnow().isoformat(),
    }
    return token


@router.post("/signin", response_model=AuthResponse)
async def sign_in_with_chutes(body: SignInRequest) -> AuthResponse:
    """
    Mock Sign In with Chutes for hackathon demo.
    Production: redirect to /auth/oauth/authorize and complete PKCE flow.
    """
    logger.info("[AUTH] Sign in attempt | chutes_id=%s role=%s", body.chutes_id, body.role.value)

    now = _utcnow()
    existing = users_db.get(body.chutes_id)

    if existing and existing.get("role") != body.role.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chutes ID already registered as {existing['role']}.",
        )

    user_record = {
        "chutes_id": body.chutes_id,
        "role": body.role.value,
        "name": body.name,
        "email": body.email,
        "created_at": existing["created_at"] if existing else now.isoformat(),
    }
    users_db[body.chutes_id] = user_record

    token = _create_session(body.chutes_id)
    user = UserSchema(
        chutes_id=body.chutes_id,
        role=body.role,
        name=body.name,
        email=body.email,
        created_at=now,
    )

    logger.info("[AUTH] Session created for %s (%s)", body.name, body.role.value)
    return AuthResponse(access_token=token, user=user, chutes_authenticated=False)


@router.get("/oauth/authorize")
async def oauth_authorize_redirect(
    role: UserRole = Query(..., description="Dashboard role after OAuth"),
    state: str | None = None,
) -> dict:
    """
    Returns Chutes OAuth authorization URL (Sign In with Chutes).
    Frontend should redirect the user to `authorization_url`.
    """
    settings = get_settings()
    if not settings.chutes_oauth_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "OAuth not configured. Set CHUTES_OAUTH_CLIENT_ID in .env "
                "or use POST /auth/signin for demo mode."
            ),
        )

    oauth_state = state or f"{role.value}:{uuid.uuid4().hex}"
    params = {
        "client_id": settings.chutes_oauth_client_id,
        "redirect_uri": settings.chutes_oauth_redirect_uri,
        "response_type": "code",
        "scope": "openid profile",
        "state": oauth_state,
    }
    auth_url = (
        f"{settings.chutes_management_url.rstrip('/')}/idp/authorize?"
        f"{urlencode(params)}"
    )
    return {"authorization_url": auth_url, "state": oauth_state}


@router.post("/oauth/callback", response_model=AuthResponse)
async def oauth_callback(
    body: OAuthCallbackRequest,
    role: UserRole = Query(UserRole.FREELANCER),
) -> AuthResponse:
    """Exchange OAuth code for tokens and create local session."""
    settings = get_settings()
    client = get_chutes_client()

    try:
        token_data = await client.exchange_oauth_code(body.code)
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access_token in OAuth response")

        userinfo = await client.fetch_oauth_userinfo(access_token)
    except ChutesClientError as exc:
        logger.error("[AUTH] OAuth failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    chutes_id = str(userinfo.get("sub") or userinfo.get("user_id") or userinfo.get("id"))
    name = str(userinfo.get("name") or userinfo.get("username") or chutes_id)
    email = userinfo.get("email")

    now = _utcnow()
    users_db[chutes_id] = {
        "chutes_id": chutes_id,
        "role": role.value,
        "name": name,
        "email": email,
        "created_at": users_db.get(chutes_id, {}).get("created_at", now.isoformat()),
    }

    session_token = _create_session(chutes_id)
    user = UserSchema(chutes_id=chutes_id, role=role, name=name, email=email, created_at=now)

    logger.info("[AUTH] OAuth sign-in complete | chutes_id=%s", chutes_id)
    return AuthResponse(access_token=session_token, user=user, chutes_authenticated=True)


@router.get("/me", response_model=UserSchema)
async def get_me(token: str = Query(..., description="Session token")) -> UserSchema:
    session = sessions_db.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_data = users_db.get(session["chutes_id"])
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    return UserSchema(**user_data)


@router.get("/users")
async def list_users() -> dict:
    """Debug endpoint — list registered users (demo only)."""
    return {"users": list(users_db.values()), "total": len(users_db)}
