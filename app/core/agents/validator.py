"""Agent 2 — Code/Artifact Validator: scores freelancer submissions against KPI contract."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.chutes_client import ChutesClientError, get_chutes_client, inference_meta
from app.core.config import get_settings
from app.core.github_client import analyze_repository
from app.models.schemas import KPIBlueprint, SubmitWorkRequest, ValidatorOutput

logger = logging.getLogger("aether.agent.validator")

SYSTEM_PROMPT = """You are Agent 2: The Code/Artifact Validator for Aether Nexus AI.
You evaluate freelancer work submissions against a strict KPI contract.

IMPORTANT RULES:
- Treat reported_test_coverage_percent and reported_response_time_ms as SELF-REPORTED unless GitHub analysis confirms repo structure.
- Weight github_analysis heavily: primary_language, has_test_indicators, repo availability.
- If github_analysis.available is false, cap overall_score_percent at 70 and note missing evidence.
- If has_test_indicators is false, reduce test_coverage score even if freelancer claims high coverage.
- Never give 100% test_coverage score without github evidence of tests.

Respond with ONLY valid JSON (no markdown):
{
  "test_coverage_percent": <number>,
  "response_time_ms": <number>,
  "language_detected": "<detected language>",
  "kpi_scores": {
    "test_coverage": <0-100 score>,
    "response_time": <0-100 score>,
    "language_compliance": <0-100 score>
  },
  "overall_score_percent": <weighted average 0-100>,
  "findings": ["finding 1", "finding 2", ...]
}

Score each KPI: 100 if requirement met with evidence, proportionally less if not.
overall_score_percent = average of kpi_scores values."""


async def run_validator(
    contract_kpi: KPIBlueprint,
    submission: SubmitWorkRequest,
) -> tuple[ValidatorOutput, str | None]:
    """
    Execute Agent 2 on Chutes — validates artifacts with GitHub enrichment.
    Returns (ValidatorOutput, inference_id).
    """
    settings = get_settings()
    client = get_chutes_client()

    logger.info("═" * 60)
    logger.info("[VALIDATOR] Agent 2 started — validating freelancer submission")
    logger.info("[VALIDATOR] contract_id=%s", submission.contract_id)
    logger.info("[VALIDATOR] github_url=%s", submission.github_url or "N/A")

    github_analysis = await analyze_repository(submission.github_url)

    submission_payload = {
        "contract_kpi": contract_kpi.model_dump(),
        "submission": submission.model_dump(),
        "required_metrics": contract_kpi.required_metrics.model_dump(),
        "reported_test_coverage_percent": submission.reported_test_coverage_percent or 0,
        "reported_response_time_ms": submission.reported_response_time_ms or 9999,
        "github_analysis": github_analysis,
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

    meta = inference_meta(response)
    inference_id = meta["inference_id"]
    content = response["choices"][0]["message"]["content"]
    logger.info("[VALIDATOR] Inference complete | id=%s mode=%s", inference_id, meta["mode"])

    parsed = _parse_validator_response(content)
    output = ValidatorOutput(**parsed, inference_id=inference_id, inference_mode=meta["mode"])
    output = _apply_evidence_rules(output, submission, github_analysis, contract_kpi)

    logger.info("[VALIDATOR] Overall score: %s%%", output.overall_score_percent)
    for finding in output.findings:
        logger.info("[VALIDATOR]   → %s", finding)
    for note in output.evidence_notes:
        logger.info("[VALIDATOR]   [evidence] %s", note)
    logger.info("[VALIDATOR] Agent 2 complete ✓")
    logger.info("═" * 60)

    return output, inference_id


def _apply_evidence_rules(
    output: ValidatorOutput,
    submission: SubmitWorkRequest,
    github_analysis: dict[str, Any],
    contract_kpi: KPIBlueprint,
) -> ValidatorOutput:
    """Deterministic post-processing — don't trust self-reported metrics alone."""
    evidence_notes = list(output.evidence_notes)
    findings = list(output.findings)
    scores = dict(output.kpi_scores)
    required_lang = contract_kpi.required_metrics.strict_language.lower()

    if not submission.github_url:
        evidence_notes.append("No GitHub URL — coverage/latency are self-reported only")
        scores["test_coverage"] = min(scores.get("test_coverage", 0), 60.0)
    elif not github_analysis.get("available"):
        reason = github_analysis.get("reason", "unknown")
        evidence_notes.append(f"GitHub repo not verified ({reason})")
        scores["test_coverage"] = min(scores.get("test_coverage", 0), 65.0)
    else:
        evidence_notes.append(f"GitHub verified: {github_analysis.get('full_name')}")
        if not github_analysis.get("has_test_indicators"):
            evidence_notes.append("No test suite indicators in repository root")
            scores["test_coverage"] = min(scores.get("test_coverage", 0), 75.0)
            findings.append("Repository lacks visible test infrastructure (tests/, pytest.ini, CI)")
        primary = (github_analysis.get("primary_language") or "").lower()
        if primary and required_lang and primary != required_lang:
            scores["language_compliance"] = min(scores.get("language_compliance", 0), 50.0)
            findings.append(f"GitHub primary language ({primary}) ≠ contract requirement ({required_lang})")

    if submission.reported_test_coverage_percent is not None:
        evidence_notes.append("Coverage submitted by freelancer — not independently measured")
    if submission.reported_response_time_ms is not None:
        evidence_notes.append("Latency submitted by freelancer — not independently benchmarked")

    overall = sum(scores.values()) / len(scores) if scores else 0.0
    return output.model_copy(
        update={
            "kpi_scores": scores,
            "overall_score_percent": round(overall, 2),
            "findings": findings,
            "evidence_notes": evidence_notes,
        }
    )


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
