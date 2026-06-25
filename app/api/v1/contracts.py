"""Contract creation and management — triggers Agent 1 (Architect)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_role
from app.core.agents.architect import run_architect
from app.core.database import append_verification_log, contracts_db, new_id, users_db
from app.models.schemas import (
    ContractListResponse,
    ContractResponse,
    ContractStatus,
    CreateContractRequest,
    UserRole,
    UserSchema,
)

logger = logging.getLogger("aether.api.contracts")
router = APIRouter(prefix="/contracts", tags=["Contracts"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_response(record: dict) -> ContractResponse:
    return ContractResponse(**record)


@router.post("/create", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    body: CreateContractRequest,
    user: UserSchema = Depends(require_role(UserRole.COMPANY)),
) -> ContractResponse:
    """
    Company creates a smart task. Agent 1 (Architect) runs on Chutes
    to convert plain-English requirements into strict JSON KPIs.
    """
    contract_id = new_id()
    now = _utcnow()

    logger.info("[CONTRACTS] Creating contract %s for company %s", contract_id, user.chutes_id)

    append_verification_log(
        contract_id,
        {
            "agent": "system",
            "step": "contract_created",
            "status": "started",
            "detail": "Company submitted raw task description",
        },
    )

    try:
        kpi_blueprint, inference_id = await run_architect(body.raw_task_description)
    except Exception as exc:
        logger.exception("[CONTRACTS] Architect agent failed")
        append_verification_log(
            contract_id,
            {
                "agent": "architect",
                "step": "kpi_generation",
                "status": "failed",
                "detail": str(exc),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent 1 (Architect) failed: {exc}",
        ) from exc

    append_verification_log(
        contract_id,
        {
            "agent": "architect",
            "step": "kpi_generation",
            "status": "completed",
            "detail": f"KPI blueprint: {kpi_blueprint.task_title}",
            "inference_id": inference_id,
            "score": 100,
        },
    )

    status_value = ContractStatus.ACTIVE if body.freelancer_chutes_id else ContractStatus.KPI_GENERATED

    record = {
        "contract_id": contract_id,
        "company_chutes_id": user.chutes_id,
        "freelancer_chutes_id": body.freelancer_chutes_id,
        "status": status_value.value,
        "raw_task_description": body.raw_task_description,
        "kpi_blueprint": kpi_blueprint.model_dump(),
        "budget_usd": body.budget_usd,
        "architect_inference_id": inference_id,
        "created_at": now,
        "updated_at": now,
    }
    contracts_db[contract_id] = record

    logger.info("[CONTRACTS] Contract %s created | status=%s", contract_id, status_value.value)
    return _to_response(record)


@router.get("/list", response_model=ContractListResponse)
async def list_contracts(
    user: UserSchema = Depends(get_current_user),
) -> ContractListResponse:
    """List contracts visible to the current user based on role."""
    results = []
    for record in contracts_db.values():
        if user.role == UserRole.COMPANY and record["company_chutes_id"] == user.chutes_id:
            results.append(_to_response(record))
        elif user.role == UserRole.FREELANCER:
            fid = record.get("freelancer_chutes_id")
            if fid == user.chutes_id or fid is None:
                results.append(_to_response(record))

    results.sort(key=lambda c: c.created_at, reverse=True)
    return ContractListResponse(contracts=results, total=len(results))


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: str,
    user: UserSchema = Depends(get_current_user),
) -> ContractResponse:
    record = contracts_db.get(contract_id)
    if not record:
        raise HTTPException(status_code=404, detail="Contract not found")

    if user.role == UserRole.COMPANY and record["company_chutes_id"] != user.chutes_id:
        raise HTTPException(status_code=403, detail="Not your contract")
    if user.role == UserRole.FREELANCER:
        fid = record.get("freelancer_chutes_id")
        if fid and fid != user.chutes_id:
            raise HTTPException(status_code=403, detail="Not assigned to you")

    return _to_response(record)


@router.post("/{contract_id}/assign/{freelancer_chutes_id}", response_model=ContractResponse)
async def assign_freelancer(
    contract_id: str,
    freelancer_chutes_id: str,
    user: UserSchema = Depends(require_role(UserRole.COMPANY)),
) -> ContractResponse:
    record = contracts_db.get(contract_id)
    if not record:
        raise HTTPException(status_code=404, detail="Contract not found")
    if record["company_chutes_id"] != user.chutes_id:
        raise HTTPException(status_code=403, detail="Not your contract")

    freelancer = users_db.get(freelancer_chutes_id)
    if not freelancer:
        raise HTTPException(status_code=404, detail="Freelancer not found. They must sign in first.")
    if freelancer.get("role") != UserRole.FREELANCER.value:
        raise HTTPException(status_code=400, detail="User is not a freelancer")

    record["freelancer_chutes_id"] = freelancer_chutes_id
    record["status"] = ContractStatus.ACTIVE.value
    record["updated_at"] = _utcnow()
    contracts_db[contract_id] = record

    logger.info("[CONTRACTS] Assigned %s to contract %s", freelancer_chutes_id, contract_id)
    return _to_response(record)
