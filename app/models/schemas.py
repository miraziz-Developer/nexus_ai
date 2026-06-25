"""Pydantic schemas and domain enums."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    COMPANY = "company"
    FREELANCER = "freelancer"


class ContractStatus(str, Enum):
    DRAFT = "draft"
    KPI_GENERATED = "kpi_generated"
    ACTIVE = "active"
    SUBMITTED = "submitted"
    VERIFYING = "verifying"
    APPROVED = "approved"
    REJECTED = "rejected"


class VerificationVerdict(str, Enum):
    APPROVED = "Approved"
    REJECTED = "Rejected"
    PENDING = "Pending"


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserSchema(BaseModel):
    chutes_id: str
    role: UserRole
    name: str
    email: str | None = None
    created_at: datetime | None = None


class SignInRequest(BaseModel):
    """Mock Sign In with Chutes — production uses OAuth PKCE flow."""
    chutes_id: str = Field(..., min_length=3, description="Chutes user ID or wallet address")
    role: UserRole
    name: str = Field(..., min_length=1)
    email: str | None = None


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSchema
    chutes_authenticated: bool = False


# ── Contracts ─────────────────────────────────────────────────────────────────

class RequiredMetrics(BaseModel):
    min_test_coverage_percent: float = Field(..., ge=0, le=100)
    max_response_time_ms: float = Field(..., gt=0)
    strict_language: str = Field(..., min_length=1)


class KPIBlueprint(BaseModel):
    task_title: str
    required_metrics: RequiredMetrics
    milestones: list[str] = Field(default_factory=list)
    raw_analysis: dict[str, Any] | None = None


class CreateContractRequest(BaseModel):
    raw_task_description: str = Field(
        ...,
        min_length=10,
        description="Plain-English task and KPI requirements from the company",
    )
    freelancer_chutes_id: str | None = Field(
        None,
        description="Optional freelancer to assign immediately",
    )
    budget_usd: float | None = None


class ContractResponse(BaseModel):
    contract_id: str
    company_chutes_id: str
    freelancer_chutes_id: str | None
    status: ContractStatus
    raw_task_description: str
    kpi_blueprint: KPIBlueprint | None = None
    budget_usd: float | None = None
    architect_inference_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ContractListResponse(BaseModel):
    contracts: list[ContractResponse]
    total: int


# ── Verification ──────────────────────────────────────────────────────────────

class SubmitWorkRequest(BaseModel):
    contract_id: str
    github_url: str | None = None
    artifact_description: str | None = None
    reported_test_coverage_percent: float | None = Field(None, ge=0, le=100)
    reported_response_time_ms: float | None = Field(None, gt=0)
    notes: str | None = None


class AgentStepLog(BaseModel):
    agent: str
    step: str
    status: str
    detail: str | None = None
    inference_id: str | None = None
    timestamp: datetime | None = None


class ValidatorOutput(BaseModel):
    test_coverage_percent: float
    response_time_ms: float
    language_detected: str
    kpi_scores: dict[str, float]
    overall_score_percent: float
    findings: list[str]
    inference_id: str | None = None


class AuditorOutput(BaseModel):
    verdict: VerificationVerdict
    consensus_score_percent: float
    summary: str
    approved_metrics: dict[str, bool]
    audit_hash: str
    inference_id: str | None = None


class VerificationResponse(BaseModel):
    contract_id: str
    status: ContractStatus
    agent_pipeline: list[AgentStepLog]
    validator_output: ValidatorOutput | None = None
    auditor_output: AuditorOutput | None = None
    on_chain_audit_id: str | None = None
    payment_recommendation_percent: float = 0.0


class VerificationStatusResponse(BaseModel):
    contract_id: str
    status: ContractStatus
    logs: list[dict[str, Any]]
    on_chain_records: list[dict[str, Any]]
