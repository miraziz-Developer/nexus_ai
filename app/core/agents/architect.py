"""Agent 1 — Legal/KPI Architect: converts plain-English tasks into strict JSON KPIs."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.chutes_client import ChutesClientError, get_chutes_client
from app.core.config import get_settings
from app.models.schemas import KPIBlueprint, RequiredMetrics

logger = logging.getLogger("aether.agent.architect")

SYSTEM_PROMPT = """You are Agent 1: The Legal/KPI Architect for Aether Nexus AI.
Your job is to analyze corporate task descriptions and convert them into strict,
measurable KPI contracts as JSON.

You MUST respond with ONLY a valid JSON object (no markdown) with this exact structure:
{
  "task_title": "short descriptive title",
  "required_metrics": {
    "min_test_coverage_percent": <number 0-100>,
    "max_response_time_ms": <positive number>,
    "strict_language": "<programming language e.g. python, typescript>"
  },
  "milestones": ["milestone 1", "milestone 2", ...]
}

Extract numeric KPIs from the text. If coverage or latency not specified, use 85% and 200ms defaults.
Infer the primary programming language from context (default: python for backend tasks)."""


async def run_architect(raw_task_description: str) -> tuple[KPIBlueprint, str | None]:
    """
    Execute Agent 1 on Chutes decentralized compute.
    Returns (KPIBlueprint, inference_id).
    """
    settings = get_settings()
    client = get_chutes_client()

    logger.info("═" * 60)
    logger.info("[ARCHITECT] Agent 1 started — parsing corporate task input")
    logger.info("[ARCHITECT] Input length: %d chars", len(raw_task_description))

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Convert this corporate task and KPI requirements into strict JSON:\n\n"
                f"{raw_task_description}"
            ),
        },
    ]

    try:
        response = await client.chat_completion(
            model=settings.architect_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            agent_name="architect",
        )
    except ChutesClientError as exc:
        logger.error("[ARCHITECT] Chutes error: %s", exc)
        raise

    inference_id = response.get("id")
    content = response["choices"][0]["message"]["content"]
    logger.info("[ARCHITECT] Raw LLM response received | inference_id=%s", inference_id)

    parsed = _parse_architect_response(content)
    blueprint = KPIBlueprint(
        task_title=parsed["task_title"],
        required_metrics=RequiredMetrics(**parsed["required_metrics"]),
        milestones=parsed.get("milestones", []),
        raw_analysis=parsed,
    )

    logger.info("[ARCHITECT] KPI Blueprint generated:")
    logger.info("[ARCHITECT]   task_title: %s", blueprint.task_title)
    logger.info(
        "[ARCHITECT]   min_test_coverage: %s%%",
        blueprint.required_metrics.min_test_coverage_percent,
    )
    logger.info(
        "[ARCHITECT]   max_response_time: %sms",
        blueprint.required_metrics.max_response_time_ms,
    )
    logger.info("[ARCHITECT]   strict_language: %s", blueprint.required_metrics.strict_language)
    logger.info("[ARCHITECT] Agent 1 complete ✓")
    logger.info("═" * 60)

    return blueprint, inference_id


def _parse_architect_response(content: str) -> dict[str, Any]:
    """Parse and validate architect JSON output with fallback normalization."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Try extracting JSON from markdown fences
        stripped = content.strip()
        if "```" in stripped:
            parts = stripped.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    data = json.loads(part)
                    break
            else:
                raise ValueError(f"Architect returned invalid JSON: {content[:200]}")
        else:
            raise ValueError(f"Architect returned invalid JSON: {content[:200]}") from None

    if "required_metrics" not in data:
        raise ValueError("Architect response missing required_metrics")

    metrics = data["required_metrics"]
    data["task_title"] = data.get("task_title") or "Untitled Task"
    data.setdefault("milestones", [])

    # Coerce types
    metrics["min_test_coverage_percent"] = float(metrics.get("min_test_coverage_percent", 85))
    metrics["max_response_time_ms"] = float(metrics.get("max_response_time_ms", 200))
    metrics["strict_language"] = str(metrics.get("strict_language", "python"))

    return data
