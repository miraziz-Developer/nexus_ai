"""SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    chutes_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    sessions: Mapped[list[SessionRow]] = relationship(back_populates="user")


class SessionRow(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    chutes_id: Mapped[str] = mapped_column(ForeignKey("users.chutes_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped[UserRow] = relationship(back_populates="sessions")


class ContractRow(Base):
    __tablename__ = "contracts"

    contract_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    company_chutes_id: Mapped[str] = mapped_column(String(128), index=True)
    freelancer_chutes_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    raw_task_description: Mapped[str] = mapped_column(Text, nullable=False)
    kpi_blueprint: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    budget_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    architect_inference_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_verification: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    logs: Mapped[list[VerificationLogRow]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    audits: Mapped[list[AuditLogRow]] = relationship(back_populates="contract", cascade="all, delete-orphan")


class VerificationLogRow(Base):
    __tablename__ = "verification_logs"

    log_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.contract_id"), index=True)
    agent: Mapped[str] = mapped_column(String(64))
    step: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    inference_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    contract: Mapped[ContractRow] = relationship(back_populates="logs")


class AuditLogRow(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.contract_id"), index=True)
    verdict: Mapped[str] = mapped_column(String(32))
    consensus_score_percent: Mapped[float] = mapped_column(Float, default=0.0)
    audit_hash: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSON)
    network: Mapped[str] = mapped_column(String(64), default="chutes-decentralized-compute")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    contract: Mapped[ContractRow] = relationship(back_populates="audits")
