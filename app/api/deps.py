"""Auth dependency helpers for protected routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import sessions_db, users_db
from app.models.schemas import UserRole, UserSchema

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UserSchema:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token. Sign in with Chutes first.",
        )

    token = credentials.credentials
    session = sessions_db.get(token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
        )

    chutes_id = session["chutes_id"]
    user_data = users_db.get(chutes_id)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    return UserSchema(**user_data)


def require_role(*roles: UserRole):
    """Dependency factory to enforce role-based access."""

    async def _checker(user: UserSchema = Depends(get_current_user)) -> UserSchema:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' not authorized for this endpoint.",
            )
        return user

    return _checker
