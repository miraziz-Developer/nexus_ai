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
    LoginRequest,
    OAuthCallbackRequest,
    RegisterRequest,
    SignInRequest,
    UserRole,
    UserSchema,
)
from app.api.deps import get_current_user
from app.repositories.deps import get_store
from app.repositories.store import NexusStore

logger = logging.getLogger("aether.api.auth")
router = APIRouter(prefix="/auth", tags=["Authentication"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _issue_session(store: NexusStore, row, *, chutes_authenticated: bool = False) -> AuthResponse:
    token = await store.create_session(row.chutes_id)
    user = UserSchema(
        chutes_id=row.chutes_id,
        role=UserRole(row.role),
        name=row.name,
        email=row.email,
        created_at=row.created_at,
    )
    return AuthResponse(access_token=token, user=user, chutes_authenticated=chutes_authenticated)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    store: Annotated[NexusStore, Depends(get_store)],
) -> AuthResponse:
    """Create a new Chutes account (company or freelancer)."""
    logger.info("[AUTH] Register | chutes_id=%s role=%s", body.chutes_id, body.role.value)

    existing = await store.get_user(body.chutes_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chutes ID already registered. Please sign in instead.",
        )

    row = await store.create_user(
        chutes_id=body.chutes_id,
        role=body.role.value,
        name=body.name,
        email=body.email,
    )
    logger.info("[AUTH] Registered %s as %s", body.chutes_id, body.role.value)
    return await _issue_session(store, row)


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    store: Annotated[NexusStore, Depends(get_store)],
) -> AuthResponse:
    """Sign in with an existing Chutes ID."""
    logger.info("[AUTH] Login | chutes_id=%s", body.chutes_id)

    row = await store.get_user(body.chutes_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found. Please register first.",
        )

    logger.info("[AUTH] Session created for %s", row.name)
    return await _issue_session(store, row)


@router.post("/signin", response_model=AuthResponse)
async def sign_in_with_chutes(
    body: SignInRequest,
    store: Annotated[NexusStore, Depends(get_store)],
) -> AuthResponse:
    """Legacy endpoint — login only (register via POST /auth/register)."""
    return await login(LoginRequest(chutes_id=body.chutes_id), store)


@router.get("/oauth/authorize")
async def oauth_authorize_redirect(
    role: UserRole = Query(...),
    state: str | None = None,
) -> dict:
    settings = get_settings()
    if not settings.chutes_oauth_client_id:
        raise HTTPException(
            status_code=501,
            detail="OAuth not configured. Set CHUTES_OAUTH_CLIENT_ID or use POST /auth/login.",
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

    existing = await store.get_user(chutes_id)
    if existing:
        row = existing
    else:
        row = await store.create_user(chutes_id=chutes_id, role=role.value, name=name, email=email)

    response = await _issue_session(store, row, chutes_authenticated=True)
    return response


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
async def list_users(
    _user: Annotated[UserSchema, Depends(get_current_user)],
    store: Annotated[NexusStore, Depends(get_store)],
) -> dict:
    users = await store.list_users()
    return {"users": users, "total": len(users)}
