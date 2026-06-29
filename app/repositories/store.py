"""Persistent data access layer (SQLite / PostgreSQL)."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chutes_client import is_mock_inference_id
from app.models.orm import AuditLogRow, ContractRow, SessionRow, UserRow, VerificationLogRow
from app.models.schemas import ContractResponse, ContractStatus, UserRole, UserSchema


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class NexusStore:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Users & sessions ─────────────────────────────────────────────────────

    async def release_lock(self) -> None:
        """Commit pending writes before long external API calls (avoids SQLite lock)."""
        await self.session.commit()

    async def create_user(
        self,
        *,
        chutes_id: str,
        role: str,
        name: str,
        email: str | None = None,
    ) -> UserRow:
        existing = await self.session.get(UserRow, chutes_id)
        if existing is not None:
            raise ValueError("Chutes ID already registered")
        row = UserRow(chutes_id=chutes_id, role=role, name=name, email=email)
        self.session.add(row)
        await self.session.flush()
        return row

    async def upsert_user(
        self,
        *,
        chutes_id: str,
        role: str,
        name: str,
        email: str | None = None,
    ) -> UserRow:
        row = await self.session.get(UserRow, chutes_id)
        if row is None:
            row = UserRow(chutes_id=chutes_id, role=role, name=name, email=email)
            self.session.add(row)
        else:
            row.name = name
            row.email = email
            if row.role != role:
                raise ValueError(f"Chutes ID already registered as {row.role}")
        await self.session.flush()
        return row

    async def get_user(self, chutes_id: str) -> UserRow | None:
        return await self.session.get(UserRow, chutes_id)

    async def user_to_schema(self, row: UserRow) -> UserSchema:
        return UserSchema(
            chutes_id=row.chutes_id,
            role=UserRole(row.role),
            name=row.name,
            email=row.email,
            created_at=row.created_at,
        )

    async def create_session(self, chutes_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self.session.add(SessionRow(token=token, chutes_id=chutes_id))
        await self.session.flush()
        return token

    async def get_session_user(self, token: str) -> UserSchema | None:
        result = await self.session.execute(
            select(UserRow).join(SessionRow).where(SessionRow.token == token)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return await self.user_to_schema(row)

    async def list_users(self) -> list[dict[str, Any]]:
        result = await self.session.execute(select(UserRow))
        return [
            {
                "chutes_id": u.chutes_id,
                "role": u.role,
                "name": u.name,
                "email": u.email,
                "created_at": u.created_at.isoformat(),
            }
            for u in result.scalars().all()
        ]

    # ── Contracts ───────────────────────────────────────────────────────────

    def contract_to_dict(self, row: ContractRow) -> dict[str, Any]:
        return {
            "contract_id": row.contract_id,
            "company_chutes_id": row.company_chutes_id,
            "freelancer_chutes_id": row.freelancer_chutes_id,
            "status": row.status,
            "raw_task_description": row.raw_task_description,
            "kpi_blueprint": row.kpi_blueprint,
            "budget_usd": row.budget_usd,
            "architect_inference_id": row.architect_inference_id,
            "last_verification": row.last_verification,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def contract_to_response(self, row: ContractRow) -> ContractResponse:
        data = self.contract_to_dict(row)
        iid = data.get("architect_inference_id")
        if iid:
            data["architect_inference_mode"] = "mock" if is_mock_inference_id(iid) else "chutes_live"
        return ContractResponse(**data)

    async def create_contract(self, **fields: Any) -> ContractRow:
        contract_id = fields.pop("contract_id", None) or new_id()
        row = ContractRow(contract_id=contract_id, **fields)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_contract(self, contract_id: str) -> ContractRow | None:
        return await self.session.get(ContractRow, contract_id)

    async def update_contract(self, row: ContractRow, **fields: Any) -> ContractRow:
        for key, value in fields.items():
            setattr(row, key, value)
        row.updated_at = _utcnow()
        await self.session.flush()
        return row

    async def list_contracts_for_user(self, user: UserSchema) -> list[ContractRow]:
        q = select(ContractRow)
        if user.role == UserRole.COMPANY:
            q = q.where(ContractRow.company_chutes_id == user.chutes_id)
        else:
            q = q.where(
                (ContractRow.freelancer_chutes_id == user.chutes_id)
                | (ContractRow.freelancer_chutes_id.is_(None))
            )
        q = q.order_by(ContractRow.created_at.desc())
        result = await self.session.execute(q)
        return list(result.scalars().all())

    # ── Verification logs ─────────────────────────────────────────────────────

    async def append_verification_log(self, contract_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        row = VerificationLogRow(
            log_id=new_id(),
            contract_id=contract_id,
            agent=entry.get("agent", "system"),
            step=entry.get("step", ""),
            status=entry.get("status", ""),
            detail=entry.get("detail"),
            inference_id=entry.get("inference_id"),
            score=entry.get("score"),
            verdict=entry.get("verdict"),
            extra={k: v for k, v in entry.items() if k not in {
                "agent", "step", "status", "detail", "inference_id", "score", "verdict",
            }},
        )
        self.session.add(row)
        await self.session.flush()
        return self._log_to_dict(row)

    async def get_verification_logs(self, contract_id: str) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(VerificationLogRow)
            .where(VerificationLogRow.contract_id == contract_id)
            .order_by(VerificationLogRow.created_at)
        )
        return [self._log_to_dict(r) for r in result.scalars().all()]

    @staticmethod
    def _log_to_dict(row: VerificationLogRow) -> dict[str, Any]:
        d = {
            "log_id": row.log_id,
            "timestamp": row.created_at.isoformat(),
            "agent": row.agent,
            "step": row.step,
            "status": row.status,
            "detail": row.detail,
            "inference_id": row.inference_id,
            "score": row.score,
            "verdict": row.verdict,
        }
        if row.extra:
            d.update(row.extra)
        return d

    # ── On-chain audit ────────────────────────────────────────────────────────

    async def append_audit_log(self, entry: dict[str, Any]) -> dict[str, Any]:
        audit_id = new_id()
        row = AuditLogRow(
            audit_id=audit_id,
            contract_id=entry["contract_id"],
            verdict=entry.get("verdict", "Unknown"),
            consensus_score_percent=float(entry.get("consensus_score_percent", 0)),
            audit_hash=entry.get("audit_hash", ""),
            payload=entry,
            network=entry.get("network", "chutes-decentralized-compute"),
        )
        self.session.add(row)
        await self.session.flush()
        return self._audit_to_dict(row)

    async def get_audit_logs(self, contract_id: str) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(AuditLogRow)
            .where(AuditLogRow.contract_id == contract_id)
            .order_by(AuditLogRow.created_at)
        )
        return [self._audit_to_dict(r) for r in result.scalars().all()]

    @staticmethod
    def _audit_to_dict(row: AuditLogRow) -> dict[str, Any]:
        base = {
            "audit_id": row.audit_id,
            "timestamp": row.created_at.isoformat(),
            "contract_id": row.contract_id,
            "verdict": row.verdict,
            "consensus_score_percent": row.consensus_score_percent,
            "audit_hash": row.audit_hash,
            "network": row.network,
            "immutable": True,
            "chain": "chutes-decentralized-compute",
        }
        base.update(row.payload)
        return base
