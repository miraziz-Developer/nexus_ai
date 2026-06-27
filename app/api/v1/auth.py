"""Sign In with Chutes — OAuth + persistent sessions."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.chutes_client import ChutesClientError, get_chutes_client
from app.core.config import get_settings
from app.models.schemas import (
    AuthResponse,
    OAuthCallbackRequest,
    SignInRequest,
    UserRole,
    UserSchema,
)
from app.repositories.deps import get_store
from app.repositories.store import NexusStore

logger = logging.getLogger("aether.api.auth")
router = APIRouter(prefix="/auth", tags=["Authentication"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/signin", response_model=AuthResponse)
async def sign_in_with_chutes(
    body: SignInRequest,
    store: Annotated[NexusStore, Depends(get_store)],
) -> AuthResponse:
    """Sign In with Chutes (demo fingerprint flow + session persistence)."""
    logger.info("[AUTH] Sign in | chutes_id=%s role=%s", body.chutes_id, body.role.value)

    existing = await store.get_user(body.chutes_id)
    if existing and existing.role != body.role.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chutes ID already registered as {existing.role}.",
        )

    try:
        await store.upsert_user(
            chutes_id=body.chutes_id,
            role=body.role.value,
            name=body.name,
            email=body.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    token = await store.create_session(body.chutes_id)
    user = UserSchema(
        chutes_id=body.chutes_id,
        role=body.role,
        name=body.name,
        email=body.email,
        created_at=existing.created_at if existing else _utcnow(),
    )
    logger.info("[AUTH] Session created for %s", body.name)
    return AuthResponse(access_token=token, user=user, chutes_authenticated=False)


@router.get("/oauth/authorize")
async def oauth_authorize_redirect(
    role: UserRole = Query(...),
    state: str | None = None,
) -> dict:
    settings = get_settings()
    if not settings.chutes_oauth_client_id:
        raise HTTPException(
            status_code=501,
            detail="OAuth not configured. Set CHUTES_OAUTH_CLIENT_ID or use POST /auth/signin.",
        )
    oauth_state = state or f"{role.value}:{uuid.uuid4().hex}"
    params = {
        "client_id": settings.chutes_oauth_client_id,
        "redirect_uri": settings.chutes_oauth_redirect_uri,
        "response_type": "code",
        "scope": "openid profile",
        "state": oauth_state,
    }
    auth_url = f"{settings.chutes_management_url.rstrip('/')}/idp/authorize?{urlencode(params)}"
    return {"authorization_url": auth_url, "state": oauth_state}


@router.post("/oauth/callback", response_model=AuthResponse)
async def oauth_callback(
    body: OAuthCallbackRequest,
    store: Annotated[NexusStore, Depends(get_store)],
    role: UserRole = Query(UserRole.FREELANCER),
) -> AuthResponse:
    client = get_chutes_client()
    try:
        token_data = await client.exchange_oauth_code(body.code)
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access_token in OAuth response")
        userinfo = await client.fetch_oauth_userinfo(access_token)
    except ChutesClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    chutes_id = str(userinfo.get("sub") or userinfo.get("user_id") or userinfo.get("id"))
    name = str(userinfo.get("name") or userinfo.get("username") or chutes_id)
    email = userinfo.get("email")

    await store.upsert_user(chutes_id=chutes_id, role=role.value, name=name, email=email)
    session_token = await store.create_session(chutes_id)
    user = UserSchema(chutes_id=chutes_id, role=role, name=name, email=email, created_at=_utcnow())
    return AuthResponse(access_token=session_token, user=user, chutes_authenticated=True)


@router.get("/me", response_model=UserSchema)
async def get_me(
    store: Annotated[NexusStore, Depends(get_store)],
    token: str = Query(...),
) -> UserSchema:
    user = await store.get_session_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


@router.get("/users")
async def list_users(store: Annotated[NexusStore, Depends(get_store)]) -> dict:
    users = await store.list_users()
    return {"users": users, "total": len(users)}
