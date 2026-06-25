"""Freelancer submission and multi-agent verification pipeline."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_role
from app.core.agents.auditor import build_consensus_graph_data, run_auditor
from app.core.agents.validator import run_validator
from app.core.database import (
    append_verification_log,
    contracts_db,
    on_chain_audit_db,
    verification_logs_db,
)
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

logger = logging.getLogger("aether.api.verify")
router = APIRouter(prefix="/verify", tags=["Verification"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/submit", response_model=VerificationResponse)
async def submit_work(
    body: SubmitWorkRequest,
    user: UserSchema = Depends(require_role(UserRole.FREELANCER)),
) -> VerificationResponse:
    """
    Freelancer submits work. Sequentially chains:
      Agent 2 (Validator) → Agent 3 (Auditor/Consensus)
    across Chutes decentralized compute infrastructure.
    """
    record = contracts_db.get(body.contract_id)
    if not record:
        raise HTTPException(status_code=404, detail="Contract not found")

    fid = record.get("freelancer_chutes_id")
    if fid and fid != user.chutes_id:
        raise HTTPException(status_code=403, detail="You are not assigned to this contract")
    if not fid:
        record["freelancer_chutes_id"] = user.chutes_id

    if not record.get("kpi_blueprint"):
        raise HTTPException(status_code=400, detail="Contract has no KPI blueprint yet")

    if record["status"] in (ContractStatus.APPROVED.value, ContractStatus.VERIFYING.value):
        if record["status"] == ContractStatus.APPROVED.value:
            raise HTTPException(status_code=409, detail="Contract already approved")

    kpi = KPIBlueprint(**record["kpi_blueprint"])
    pipeline: list[AgentStepLog] = []
    now = _utcnow()

    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║  MULTI-AGENT VERIFICATION PIPELINE STARTED                ║")
    logger.info("║  contract_id: %-42s ║", body.contract_id[:42])
    logger.info("╚" + "═" * 58 + "╝")

    record["status"] = ContractStatus.VERIFYING.value
    record["updated_at"] = now
    contracts_db[body.contract_id] = record

    append_verification_log(
        body.contract_id,
        {
            "agent": "system",
            "step": "submission_received",
            "status": "started",
            "detail": f"Freelancer {user.chutes_id} submitted work",
        },
    )
    pipeline.append(
        AgentStepLog(
            agent="system",
            step="submission_received",
            status="completed",
            detail="Work submission received",
            timestamp=now,
        )
    )

    # ── Agent 2: Validator ────────────────────────────────────────────────
    append_verification_log(
        body.contract_id,
        {"agent": "validator", "step": "artifact_validation", "status": "running"},
    )
    pipeline.append(
        AgentStepLog(agent="validator", step="artifact_validation", status="running", timestamp=now)
    )

    try:
        validator_output, validator_inference_id = await run_validator(kpi, body)
    except Exception as exc:
        logger.exception("[VERIFY] Validator agent failed")
        record["status"] = ContractStatus.REJECTED.value
        contracts_db[body.contract_id] = record
        append_verification_log(
            body.contract_id,
            {"agent": "validator", "step": "artifact_validation", "status": "failed", "detail": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent 2 (Validator) failed: {exc}",
        ) from exc

    append_verification_log(
        body.contract_id,
        {
            "agent": "validator",
            "step": "artifact_validation",
            "status": "completed",
            "detail": f"Score: {validator_output.overall_score_percent}%",
            "inference_id": validator_inference_id,
            "score": validator_output.overall_score_percent,
        },
    )
    pipeline.append(
        AgentStepLog(
            agent="validator",
            step="artifact_validation",
            status="completed",
            detail=f"Overall score: {validator_output.overall_score_percent}%",
            inference_id=validator_inference_id,
            timestamp=_utcnow(),
        )
    )

    # ── Agent 3: Auditor / Consensus ──────────────────────────────────────
    append_verification_log(
        body.contract_id,
        {"agent": "auditor", "step": "consensus_review", "status": "running"},
    )
    pipeline.append(
        AgentStepLog(agent="auditor", step="consensus_review", status="running", timestamp=_utcnow())
    )

    try:
        auditor_output, auditor_inference_id, on_chain_record = await run_auditor(
            kpi, validator_output, body.contract_id
        )
    except Exception as exc:
        logger.exception("[VERIFY] Auditor agent failed")
        record["status"] = ContractStatus.REJECTED.value
        contracts_db[body.contract_id] = record
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent 3 (Auditor) failed: {exc}",
        ) from exc

    append_verification_log(
        body.contract_id,
        {
            "agent": "auditor",
            "step": "consensus_review",
            "status": "completed",
            "detail": auditor_output.summary,
            "inference_id": auditor_inference_id,
            "score": auditor_output.consensus_score_percent,
            "verdict": auditor_output.verdict.value,
        },
    )
    pipeline.append(
        AgentStepLog(
            agent="auditor",
            step="consensus_review",
            status="completed",
            detail=auditor_output.summary,
            inference_id=auditor_inference_id,
            timestamp=_utcnow(),
        )
    )

    final_status = (
        ContractStatus.APPROVED
        if auditor_output.verdict == VerificationVerdict.APPROVED
        else ContractStatus.REJECTED
    )
    payment_pct = auditor_output.consensus_score_percent if final_status == ContractStatus.APPROVED else 0.0

    record["status"] = final_status.value
    record["updated_at"] = _utcnow()
    record["last_verification"] = {
        "validator": validator_output.model_dump(),
        "auditor": auditor_output.model_dump(),
        "on_chain_audit_id": on_chain_record["audit_id"],
    }
    contracts_db[body.contract_id] = record

    logger.info("[VERIFY] Pipeline complete | verdict=%s | payment=%s%%", final_status.value, payment_pct)

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
    user: UserSchema = Depends(get_current_user),
) -> VerificationStatusResponse:
    """Live audit tracking — agent steps and on-chain records for dashboard."""
    record = contracts_db.get(contract_id)
    if not record:
        raise HTTPException(status_code=404, detail="Contract not found")

    if user.role == UserRole.COMPANY and record["company_chutes_id"] != user.chutes_id:
        raise HTTPException(status_code=403, detail="Not your contract")
    if user.role == UserRole.FREELANCER:
        fid = record.get("freelancer_chutes_id")
        if fid and fid != user.chutes_id:
            raise HTTPException(status_code=403, detail="Not assigned to you")

    logs = verification_logs_db.get(contract_id, [])
    chain_records = [r for r in on_chain_audit_db if r.get("contract_id") == contract_id]

    return VerificationStatusResponse(
        contract_id=contract_id,
        status=ContractStatus(record["status"]),
        logs=logs,
        on_chain_records=chain_records,
    )


@router.get("/consensus-graph/{contract_id}")
async def consensus_graph(
    contract_id: str,
    user: UserSchema = Depends(get_current_user),
) -> dict:
    """Chart data for live agent consensus visualization on dashboard."""
    record = contracts_db.get(contract_id)
    if not record:
        raise HTTPException(status_code=404, detail="Contract not found")

    logs = verification_logs_db.get(contract_id, [])
    graph = build_consensus_graph_data(logs)

    last_ver = record.get("last_verification", {})
    graph["verdict"] = last_ver.get("auditor", {}).get("verdict")
    graph["payment_recommendation_percent"] = (
        last_ver.get("auditor", {}).get("consensus_score_percent", 0)
        if last_ver.get("auditor", {}).get("verdict") == "Approved"
        else 0
    )
    return graph
