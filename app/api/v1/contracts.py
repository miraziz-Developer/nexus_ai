"""Contract creation and management — triggers Agent 1 (Architect)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_role
from app.core.agents.architect import run_architect
from app.core.chutes_client import is_mock_inference_id
from app.models.schemas import (
    ContractListResponse,
    ContractResponse,
    ContractStatus,
    CreateContractRequest,
    UserRole,
    UserSchema,
)
from app.repositories.deps import get_store
from app.repositories.store import NexusStore, new_id

logger = logging.getLogger("aether.api.contracts")
router = APIRouter(prefix="/contracts", tags=["Contracts"])


@router.post("/create", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    body: CreateContractRequest,
    user: Annotated[UserSchema, Depends(require_role(UserRole.COMPANY))],
    store: Annotated[NexusStore, Depends(get_store)],
) -> ContractResponse:
    contract_id = new_id()
    logger.info("[CONTRACTS] Creating %s for %s", contract_id, user.chutes_id)

    await store.append_verification_log(
        contract_id,
        {"agent": "system", "step": "contract_created", "status": "started",
         "detail": "Company submitted raw task description"},
    )
    await store.release_lock()

    try:
        kpi_blueprint, inference_id = await run_architect(body.raw_task_description)
    except Exception as exc:
        logger.exception("[CONTRACTS] Architect failed")
        await store.append_verification_log(
            contract_id,
            {"agent": "architect", "step": "kpi_generation", "status": "failed", "detail": str(exc)},
        )
        raise HTTPException(status_code=502, detail=f"Agent 1 (Architect) failed: {exc}") from exc

    inference_mode = "mock" if is_mock_inference_id(inference_id) else "chutes_live"
    await store.append_verification_log(
        contract_id,
        {
            "agent": "architect", "step": "kpi_generation", "status": "completed",
            "detail": f"KPI blueprint: {kpi_blueprint.task_title} [{inference_mode}]",
            "inference_id": inference_id,
            "inference_mode": inference_mode,
        },
    )

    status_value = ContractStatus.ACTIVE if body.freelancer_chutes_id else ContractStatus.KPI_GENERATED

    if body.freelancer_chutes_id:
        freelancer = await store.get_user(body.freelancer_chutes_id)
        if not freelancer:
            raise HTTPException(404, "Freelancer not found. They must sign in first.")
        if freelancer.role != UserRole.FREELANCER.value:
            raise HTTPException(400, "User is not a freelancer")

    row = await store.create_contract(
        contract_id=contract_id,
        company_chutes_id=user.chutes_id,
        freelancer_chutes_id=body.freelancer_chutes_id,
        status=status_value.value,
        raw_task_description=body.raw_task_description,
        kpi_blueprint=kpi_blueprint.model_dump(),
        budget_usd=body.budget_usd,
        architect_inference_id=inference_id,
    )
    logger.info("[CONTRACTS] Created %s | status=%s", contract_id, status_value.value)
    return store.contract_to_response(row)


@router.get("/list", response_model=ContractListResponse)
async def list_contracts(
    user: Annotated[UserSchema, Depends(get_current_user)],
    store: Annotated[NexusStore, Depends(get_store)],
) -> ContractListResponse:
    rows = await store.list_contracts_for_user(user)
    contracts = [store.contract_to_response(r) for r in rows]
    return ContractListResponse(contracts=contracts, total=len(contracts))


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: str,
    user: Annotated[UserSchema, Depends(get_current_user)],
    store: Annotated[NexusStore, Depends(get_store)],
) -> ContractResponse:
    row = await store.get_contract(contract_id)
    if not row:
        raise HTTPException(404, "Contract not found")
    _authorize_contract_access(user, row)
    return store.contract_to_response(row)


@router.post("/{contract_id}/assign/{freelancer_chutes_id}", response_model=ContractResponse)
async def assign_freelancer(
    contract_id: str,
    freelancer_chutes_id: str,
    user: Annotated[UserSchema, Depends(require_role(UserRole.COMPANY))],
    store: Annotated[NexusStore, Depends(get_store)],
) -> ContractResponse:
    row = await store.get_contract(contract_id)
    if not row:
        raise HTTPException(404, "Contract not found")
    if row.company_chutes_id != user.chutes_id:
        raise HTTPException(403, "Not your contract")

    freelancer = await store.get_user(freelancer_chutes_id)
    if not freelancer:
        raise HTTPException(404, "Freelancer not found. They must sign in first.")
    if freelancer.role != UserRole.FREELANCER.value:
        raise HTTPException(400, "User is not a freelancer")

    row = await store.update_contract(
        row,
        freelancer_chutes_id=freelancer_chutes_id,
        status=ContractStatus.ACTIVE.value,
    )
    return store.contract_to_response(row)


def _authorize_contract_access(user: UserSchema, row) -> None:
    if user.role == UserRole.COMPANY and row.company_chutes_id != user.chutes_id:
        raise HTTPException(403, "Not your contract")
    if user.role == UserRole.FREELANCER:
        if row.freelancer_chutes_id and row.freelancer_chutes_id != user.chutes_id:
            raise HTTPException(403, "Not assigned to you")
