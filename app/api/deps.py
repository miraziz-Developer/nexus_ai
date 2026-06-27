"""Auth dependency helpers for protected routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.schemas import UserRole, UserSchema
from app.repositories.deps import get_store
from app.repositories.store import NexusStore

security = HTTPBearer(auto_error=False)


async def get_current_user(
    store: Annotated[NexusStore, Depends(get_store)],
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UserSchema:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token. Sign in with Chutes first.",
        )

    user = await store.get_session_user(credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
        )
    return user


def require_role(*roles: UserRole):
    async def _checker(user: UserSchema = Depends(get_current_user)) -> UserSchema:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' not authorized for this endpoint.",
            )
        return user

    return _checker
