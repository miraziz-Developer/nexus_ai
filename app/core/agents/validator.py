"""Agent 2 — Code/Artifact Validator: scores freelancer submissions against KPI contract."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.chutes_client import ChutesClientError, get_chutes_client
from app.core.config import get_settings
from app.models.schemas import KPIBlueprint, SubmitWorkRequest, ValidatorOutput

logger = logging.getLogger("aether.agent.validator")

SYSTEM_PROMPT = """You are Agent 2: The Code/Artifact Validator for Aether Nexus AI.
You evaluate freelancer work submissions against a strict KPI contract.

Analyze the submission (GitHub URL, artifact description, reported metrics) and score it.

Respond with ONLY valid JSON (no markdown):
{
  "test_coverage_percent": <measured or reported coverage>,
  "response_time_ms": <measured or reported latency>,
  "language_detected": "<detected language>",
  "kpi_scores": {
    "test_coverage": <0-100 score>,
    "response_time": <0-100 score>,
    "language_compliance": <0-100 score>
  },
  "overall_score_percent": <weighted average 0-100>,
  "findings": ["finding 1", "finding 2", ...]
}

Score each KPI: 100 if requirement met, proportionally less if not.
overall_score_percent = average of kpi_scores values."""


async def run_validator(
    contract_kpi: KPIBlueprint,
    submission: SubmitWorkRequest,
) -> tuple[ValidatorOutput, str | None]:
    """
    Execute Agent 2 on Chutes — on-chain inference for artifact validation.
    Returns (ValidatorOutput, inference_id).
    """
    settings = get_settings()
    client = get_chutes_client()

    logger.info("═" * 60)
    logger.info("[VALIDATOR] Agent 2 started — validating freelancer submission")
    logger.info("[VALIDATOR] contract_id=%s", submission.contract_id)
    logger.info("[VALIDATOR] github_url=%s", submission.github_url or "N/A")

    submission_payload = {
        "contract_kpi": contract_kpi.model_dump(),
        "submission": submission.model_dump(),
        "required_metrics": contract_kpi.required_metrics.model_dump(),
        "reported_test_coverage_percent": submission.reported_test_coverage_percent or 0,
        "reported_response_time_ms": submission.reported_response_time_ms or 9999,
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Validate this submission against the KPI contract:\n\n"
                f"{json.dumps(submission_payload, indent=2)}"
            ),
        },
    ]

    try:
        response = await client.chat_completion(
            model=settings.validator_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.15,
            agent_name="validator",
        )
    except ChutesClientError as exc:
        logger.error("[VALIDATOR] Chutes error: %s", exc)
        raise

    inference_id = response.get("id")
    content = response["choices"][0]["message"]["content"]
    logger.info("[VALIDATOR] Inference complete | id=%s", inference_id)

    parsed = _parse_validator_response(content)
    output = ValidatorOutput(**parsed, inference_id=inference_id)

    logger.info("[VALIDATOR] Overall score: %s%%", output.overall_score_percent)
    for finding in output.findings:
        logger.info("[VALIDATOR]   → %s", finding)
    logger.info("[VALIDATOR] Agent 2 complete ✓")
    logger.info("═" * 60)

    return output, inference_id


def _parse_validator_response(content: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Validator returned invalid JSON: {content[:200]}") from exc

    data.setdefault("findings", [])
    data.setdefault("kpi_scores", {})
    data["test_coverage_percent"] = float(data.get("test_coverage_percent", 0))
    data["response_time_ms"] = float(data.get("response_time_ms", 0))
    data["language_detected"] = str(data.get("language_detected", "unknown"))
    data["overall_score_percent"] = float(data.get("overall_score_percent", 0))

    for key in ("test_coverage", "response_time", "language_compliance"):
        if key not in data["kpi_scores"]:
            data["kpi_scores"][key] = 0.0
        else:
            data["kpi_scores"][key] = float(data["kpi_scores"][key])

    return data
