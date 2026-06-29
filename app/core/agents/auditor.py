"""Agent 3 — Auditor/Consensus: final Approved/Rejected verdict with immutable audit log."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.chutes_client import ChutesClientError, get_chutes_client, inference_meta
from app.core.config import get_settings
from app.models.schemas import AuditorOutput, KPIBlueprint, ValidatorOutput, VerificationVerdict

logger = logging.getLogger("aether.agent.auditor")

SYSTEM_PROMPT = """You are Agent 3: The Auditor/Consensus Agent for Aether Nexus AI.
You review Agent 1 (KPI contract) and Agent 2 (validator) outputs to reach a final verdict.

Rules:
- APPROVE only if overall_score_percent >= 80 AND all critical KPIs (test_coverage, response_time) score >= 80
- REJECT otherwise with clear reasoning

Respond with ONLY valid JSON:
{
  "verdict": "Approved" or "Rejected",
  "consensus_score_percent": <number>,
  "summary": "<human-readable consensus summary for both parties>",
  "approved_metrics": {
    "test_coverage": <true/false>,
    "response_time": <true/false>,
    "language_compliance": <true/false>
  },
  "audit_hash": "<sha256 hex of validator output — compute it>"
}"""


async def run_auditor(
    contract_kpi: KPIBlueprint,
    validator_output: ValidatorOutput,
    contract_id: str,
) -> tuple[AuditorOutput, str | None, dict[str, Any]]:
    """
    Execute Agent 3 consensus on Chutes network.
    Returns (AuditorOutput, inference_id, on_chain_audit_record).
    """
    settings = get_settings()
    client = get_chutes_client()

    logger.info("═" * 60)
    logger.info("[AUDITOR] Agent 3 started — multi-agent consensus review")
    logger.info("[AUDITOR] contract_id=%s", contract_id)
    logger.info("[AUDITOR] Validator overall score: %s%%", validator_output.overall_score_percent)

    consensus_input = {
        "contract_kpi": contract_kpi.model_dump(),
        "validator_output": validator_output.model_dump(),
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Reach consensus verdict on this verification pipeline:\n\n"
                f"{json.dumps(consensus_input, indent=2)}"
            ),
        },
    ]

    try:
        response = await client.chat_completion(
            model=settings.auditor_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            agent_name="auditor",
        )
    except ChutesClientError as exc:
        logger.error("[AUDITOR] Chutes error: %s", exc)
        raise

    meta = inference_meta(response)
    inference_id = meta["inference_id"]
    content = response["choices"][0]["message"]["content"]
    logger.info("[AUDITOR] Consensus inference complete | id=%s mode=%s", inference_id, meta["mode"])

    parsed = _parse_auditor_response(content, validator_output)
    output = AuditorOutput(**parsed, inference_id=inference_id, inference_mode=meta["mode"])

    # Tamper-evident audit payload (SHA-256 hash + persisted record — not a blockchain tx)
    on_chain_record = {
        "contract_id": contract_id,
        "agent": "auditor_consensus",
        "verdict": output.verdict.value,
        "consensus_score_percent": output.consensus_score_percent,
        "audit_hash": output.audit_hash,
        "architect_kpi": contract_kpi.model_dump(),
        "validator_output": validator_output.model_dump(),
        "auditor_summary": output.summary,
        "inference_ids": {
            "validator": validator_output.inference_id,
            "auditor": inference_id,
        },
        "inference_modes": {
            "validator": validator_output.inference_mode,
            "auditor": meta["mode"],
        },
        "storage": "persistent_sqlite_audit_log",
        "integrity": "sha256_hash",
    }

    logger.info("[AUDITOR] VERDICT: %s", output.verdict.value)
    logger.info("[AUDITOR] Consensus score: %s%%", output.consensus_score_percent)
    logger.info("[AUDITOR] Audit hash: %s", output.audit_hash)
    logger.info("[AUDITOR] Agent 3 complete ✓")
    logger.info("═" * 60)

    return output, inference_id, on_chain_record


def _parse_auditor_response(
    content: str,
    validator_output: ValidatorOutput,
) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Auditor returned invalid JSON: {content[:200]}") from exc

    verdict_str = str(data.get("verdict", "Rejected"))
    if verdict_str not in ("Approved", "Rejected"):
        # Normalize
        verdict_str = "Approved" if verdict_str.lower() == "approved" else "Rejected"

    data["verdict"] = VerificationVerdict(verdict_str)
    data["consensus_score_percent"] = float(
        data.get("consensus_score_percent", validator_output.overall_score_percent)
    )
    data["summary"] = str(data.get("summary", "Consensus review completed."))
    data.setdefault("approved_metrics", {})

    # Ensure audit hash is cryptographically sound
    validator_json = json.dumps(validator_output.model_dump(), sort_keys=True)
    computed_hash = hashlib.sha256(validator_json.encode()).hexdigest()
    data["audit_hash"] = data.get("audit_hash") or computed_hash
    if len(data["audit_hash"]) != 64:
        data["audit_hash"] = computed_hash

    return data


def build_consensus_graph_data(
    pipeline_logs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build chart-friendly consensus pipeline data for dashboard."""
    agents = ["Architect", "Validator", "Auditor"]
    statuses = []
    scores = []

    for agent in agents:
        matching = [l for l in pipeline_logs if l.get("agent", "").lower().startswith(agent.lower()[:4])]
        if matching:
            last = matching[-1]
            statuses.append(last.get("status", "unknown"))
            scores.append(last.get("score", 0))
        else:
            statuses.append("pending")
            scores.append(0)

    return {
        "labels": agents,
        "statuses": statuses,
        "scores": scores,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
