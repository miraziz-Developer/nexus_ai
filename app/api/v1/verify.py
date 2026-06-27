"""Freelancer submission and multi-agent verification pipeline."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_role
from app.api.v1.contracts import _authorize_contract_access
from app.core.agents.auditor import build_consensus_graph_data, run_auditor
from app.core.agents.validator import run_validator
from app.models.schemas import (
    AgentStepLog,
    ContractStatus,
    KPIBlueprint,
    SubmitWorkRequest,
    UserRole,
    UserSchema,
    VerificationResponse,
    VerificationStatusResponse,
    VerificationVerdict,
)
from app.repositories.deps import get_store
from app.repositories.store import NexusStore

logger = logging.getLogger("aether.api.verify")
router = APIRouter(prefix="/verify", tags=["Verification"])


@router.post("/submit", response_model=VerificationResponse)
async def submit_work(
    body: SubmitWorkRequest,
    user: Annotated[UserSchema, Depends(require_role(UserRole.FREELANCER))],
    store: Annotated[NexusStore, Depends(get_store)],
) -> VerificationResponse:
    row = await store.get_contract(body.contract_id)
    if not row:
        raise HTTPException(404, "Contract not found")

    if row.freelancer_chutes_id and row.freelancer_chutes_id != user.chutes_id:
        raise HTTPException(403, "You are not assigned to this contract")
    if not row.freelancer_chutes_id:
        row = await store.update_contract(row, freelancer_chutes_id=user.chutes_id)

    if not row.kpi_blueprint:
        raise HTTPException(400, "Contract has no KPI blueprint yet")
    if row.status == ContractStatus.APPROVED.value:
        raise HTTPException(409, "Contract already approved")
    if row.status == ContractStatus.VERIFYING.value:
        raise HTTPException(409, "Verification already in progress")

    kpi = KPIBlueprint(**row.kpi_blueprint)
    pipeline: list[AgentStepLog] = []

    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║  MULTI-AGENT VERIFICATION PIPELINE STARTED                ║")
    logger.info("║  contract_id: %-42s ║", body.contract_id[:42])
    logger.info("╚" + "═" * 58 + "╝")

    row = await store.update_contract(row, status=ContractStatus.VERIFYING.value)

    await store.append_verification_log(
        body.contract_id,
        {"agent": "system", "step": "submission_received", "status": "completed",
         "detail": f"Freelancer {user.chutes_id} submitted work"},
    )
    pipeline.append(AgentStepLog(
        agent="system", step="submission_received", status="completed",
        detail="Work submission received",
    ))

    await store.append_verification_log(
        body.contract_id,
        {"agent": "validator", "step": "artifact_validation", "status": "running"},
    )
    pipeline.append(AgentStepLog(agent="validator", step="artifact_validation", status="running"))

    try:
        validator_output, validator_inference_id = await run_validator(kpi, body)
    except Exception as exc:
        logger.exception("[VERIFY] Validator failed")
        await store.update_contract(row, status=ContractStatus.REJECTED.value)
        await store.append_verification_log(
            body.contract_id,
            {"agent": "validator", "step": "artifact_validation", "status": "failed", "detail": str(exc)},
        )
        raise HTTPException(502, detail=f"Agent 2 (Validator) failed: {exc}") from exc

    await store.append_verification_log(
        body.contract_id,
        {
            "agent": "validator", "step": "artifact_validation", "status": "completed",
            "detail": f"Score: {validator_output.overall_score_percent}%",
            "inference_id": validator_inference_id,
            "score": validator_output.overall_score_percent,
        },
    )
    pipeline.append(AgentStepLog(
        agent="validator", step="artifact_validation", status="completed",
        detail=f"Overall score: {validator_output.overall_score_percent}%",
        inference_id=validator_inference_id,
    ))

    await store.append_verification_log(
        body.contract_id,
        {"agent": "auditor", "step": "consensus_review", "status": "running"},
    )
    pipeline.append(AgentStepLog(agent="auditor", step="consensus_review", status="running"))

    try:
        auditor_output, auditor_inference_id, audit_payload = await run_auditor(
            kpi, validator_output, body.contract_id
        )
        on_chain_record = await store.append_audit_log(audit_payload)
    except Exception as exc:
        logger.exception("[VERIFY] Auditor failed")
        await store.update_contract(row, status=ContractStatus.REJECTED.value)
        raise HTTPException(502, detail=f"Agent 3 (Auditor) failed: {exc}") from exc

    await store.append_verification_log(
        body.contract_id,
        {
            "agent": "auditor", "step": "consensus_review", "status": "completed",
            "detail": auditor_output.summary,
            "inference_id": auditor_inference_id,
            "score": auditor_output.consensus_score_percent,
            "verdict": auditor_output.verdict.value,
        },
    )
    pipeline.append(AgentStepLog(
        agent="auditor", step="consensus_review", status="completed",
        detail=auditor_output.summary, inference_id=auditor_inference_id,
    ))

    final_status = (
        ContractStatus.APPROVED
        if auditor_output.verdict == VerificationVerdict.APPROVED
        else ContractStatus.REJECTED
    )
    payment_pct = auditor_output.consensus_score_percent if final_status == ContractStatus.APPROVED else 0.0

    await store.update_contract(
        row,
        status=final_status.value,
        last_verification={
            "validator": validator_output.model_dump(),
            "auditor": auditor_output.model_dump(),
            "on_chain_audit_id": on_chain_record["audit_id"],
        },
    )

    logger.info("[VERIFY] Complete | verdict=%s | payment=%s%%", final_status.value, payment_pct)

    return VerificationResponse(
        contract_id=body.contract_id,
        status=final_status,
        agent_pipeline=pipeline,
        validator_output=validator_output,
        auditor_output=auditor_output,
        on_chain_audit_id=on_chain_record["audit_id"],
        payment_recommendation_percent=payment_pct,
    )


@router.get("/status/{contract_id}", response_model=VerificationStatusResponse)
async def verification_status(
    contract_id: str,
    user: Annotated[UserSchema, Depends(get_current_user)],
    store: Annotated[NexusStore, Depends(get_store)],
) -> VerificationStatusResponse:
    row = await store.get_contract(contract_id)
    if not row:
        raise HTTPException(404, "Contract not found")
    _authorize_contract_access(user, row)

    logs = await store.get_verification_logs(contract_id)
    chain_records = await store.get_audit_logs(contract_id)
    return VerificationStatusResponse(
        contract_id=contract_id,
        status=ContractStatus(row.status),
        logs=logs,
        on_chain_records=chain_records,
    )


@router.get("/consensus-graph/{contract_id}")
async def consensus_graph(
    contract_id: str,
    user: Annotated[UserSchema, Depends(get_current_user)],
    store: Annotated[NexusStore, Depends(get_store)],
) -> dict:
    row = await store.get_contract(contract_id)
    if not row:
        raise HTTPException(404, "Contract not found")
    _authorize_contract_access(user, row)

    logs = await store.get_verification_logs(contract_id)
    graph = build_consensus_graph_data(logs)
    last_ver = row.last_verification or {}
    graph["verdict"] = last_ver.get("auditor", {}).get("verdict")
    graph["payment_recommendation_percent"] = (
        last_ver.get("auditor", {}).get("consensus_score_percent", 0)
        if last_ver.get("auditor", {}).get("verdict") == "Approved"
        else 0
    )
    return graph
