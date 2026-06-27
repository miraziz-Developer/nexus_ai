"""Repository dependency injection."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.repositories.store import NexusStore


async def get_store(session: Annotated[AsyncSession, Depends(get_session)]) -> NexusStore:
    return NexusStore(session)
