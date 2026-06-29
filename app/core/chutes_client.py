"""Asynchronous HTTP client for Chutes decentralized compute network."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger("aether.chutes")


class ChutesClientError(Exception):
    """Raised when Chutes API communication fails."""

    def __init__(self, message: str, status_code: int | None = None, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class ChutesClient:
    """
    Async client for Chutes OpenAI-compatible inference and management APIs.
    Falls back to deterministic mock responses when MOCK_CHUTES_WHEN_NO_KEY=true
    or when CHUTES_FALLBACK_ON_ERROR=true and the live API returns quota/balance errors.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: httpx.AsyncClient | None = None
        self.last_inference_mode: str = "unknown"
        self.fallback_count: int = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.settings.has_chutes_api_key:
                headers["Authorization"] = f"Bearer {self.settings.chutes_api_key}"
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                headers=headers,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _mock_inference_id(self, prefix: str) -> str:
        return f"mock-chutes-{prefix}-{uuid.uuid4().hex[:12]}"

    async def _return_mock(
        self,
        agent_name: str,
        model: str,
        messages: list[dict[str, str]],
        *,
        reason: str,
        inference_id: str | None = None,
    ) -> dict[str, Any]:
        inference_id = inference_id or self._mock_inference_id(agent_name)
        logger.warning("[%s] MOCK inference (%s) — model=%s", agent_name, reason, model)
        self.last_inference_mode = "mock"
        self.fallback_count += 1
        content = await self._mock_response(agent_name, messages)
        return {
            "id": inference_id,
            "object": "chat.completion",
            "model": model,
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "_mock": True,
            "_fallback_reason": reason,
        }

    @staticmethod
    def _should_fallback(status_code: int, body: str) -> bool:
        if status_code in (402, 429, 503):
            return True
        lower = body.lower()
        return any(
            phrase in lower
            for phrase in (
                "quota exceeded",
                "balance is $0",
                "insufficient",
                "model not found",
                "payment",
            )
        )

    async def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.2,
        agent_name: str = "agent",
    ) -> dict[str, Any]:
        """
        Run on-chain style inference via Chutes llm.chutes.ai/v1/chat/completions.
        Returns OpenAI-compatible response dict with inference_id for audit trail.
        """
        inference_id = self._mock_inference_id(agent_name)

        if self.settings.use_mock_inference:
            return await self._return_mock(
                agent_name, model, messages, reason="no_api_key", inference_id=inference_id
            )

        url = f"{self.settings.chutes_inference_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        logger.info("[%s] Chutes inference → %s | model=%s", agent_name, url, model)
        client = await self._get_client()

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            inference_id = data.get("id", inference_id)
            self.last_inference_mode = "chutes_live"
            logger.info("[%s] Chutes inference OK | id=%s", agent_name, inference_id)
            return data
        except httpx.HTTPStatusError as exc:
            body = exc.response.text
            logger.error("[%s] Chutes HTTP %s: %s", agent_name, exc.response.status_code, body)
            if self.settings.allow_chutes_fallback and self._should_fallback(
                exc.response.status_code, body
            ):
                return await self._return_mock(
                    agent_name,
                    model,
                    messages,
                    reason=f"api_error_{exc.response.status_code}",
                    inference_id=inference_id,
                )
            raise ChutesClientError(
                f"Chutes inference failed: HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
                detail=body,
            ) from exc
        except httpx.RequestError as exc:
            logger.error("[%s] Chutes request error: %s", agent_name, exc)
            if self.settings.allow_chutes_fallback:
                return await self._return_mock(
                    agent_name, model, messages, reason="network_error", inference_id=inference_id
                )
            raise ChutesClientError(f"Chutes network error: {exc}") from exc

    async def _mock_response(self, agent_name: str, messages: list[dict[str, str]]) -> str:
        """Deterministic mock for demo without API key."""
        user_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_content = msg.get("content", "")
                break

        payload = self._extract_json_payload(user_content)

        if agent_name == "architect":
            # Use original task text before JSON wrapper if present
            raw_text = user_content
            if "into strict JSON:" in raw_text:
                raw_text = raw_text.split("into strict JSON:", 1)[-1].strip()
            return json.dumps(self._mock_architect_json(raw_text))
        if agent_name == "validator":
            return json.dumps(self._mock_validator_json(json.dumps(payload) if payload else user_content))
        if agent_name == "auditor":
            return json.dumps(self._mock_auditor_json(json.dumps(payload) if payload else user_content))
        return json.dumps({"status": "ok", "agent": agent_name})

    def _extract_json_payload(self, text: str) -> dict[str, Any]:
        """Extract JSON object from agent prompt text."""
        if not text:
            return {}
        # Try whole string first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Find first { ... } block (greedy enough for nested objects)
        start = text.find("{")
        if start == -1:
            return {}
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        return {}
        return {}

    def _mock_architect_json(self, raw_text: str) -> dict[str, Any]:
        text_lower = raw_text.lower()
        coverage = 85.0
        response_ms = 200.0
        language = "python"

        if "85" in raw_text or "coverage" in text_lower:
            for token in raw_text.replace("%", " ").split():
                try:
                    val = float(token)
                    if 50 <= val <= 100:
                        coverage = val
                        break
                except ValueError:
                    pass
        if "200" in raw_text or "ms" in text_lower:
            for token in raw_text.replace("ms", " ").split():
                try:
                    val = float(token)
                    if 10 <= val <= 5000:
                        response_ms = val
                        break
                except ValueError:
                    pass
        if "fastapi" in text_lower or "python" in text_lower:
            language = "python"
        elif "typescript" in text_lower or "node" in text_lower:
            language = "typescript"
        elif "rust" in text_lower:
            language = "rust"

        # Use first sentence of actual task, skip prompt boilerplate
        clean = raw_text.strip()
        for prefix in ("Convert this corporate task", "We need", "Biz", "Our team"):
            if clean.lower().startswith(prefix.lower()):
                break
        title = clean.split(".")[0][:80] or "Smart Contract Task"
        if len(title) > 60 and "We need" in clean:
            title = clean.split("\n")[-1].strip()[:80]

        return {
            "task_title": title,
            "required_metrics": {
                "min_test_coverage_percent": coverage,
                "max_response_time_ms": response_ms,
                "strict_language": language,
            },
            "milestones": [
                "Repository scaffold with agreed stack",
                "Core API endpoints implemented",
                f"Test coverage ≥ {coverage}%",
                f"API p95 latency ≤ {response_ms}ms",
                "Final submission and documentation",
            ],
        }

    def _mock_validator_json(self, payload_text: str) -> dict[str, Any]:
        data = self._extract_json_payload(payload_text)
        if not data:
            try:
                data = json.loads(payload_text)
            except json.JSONDecodeError:
                data = {}

        submission = data.get("submission", data)
        contract_kpi = data.get("contract_kpi", {})
        required = data.get("required_metrics") or contract_kpi.get("required_metrics", {})

        reported_cov = float(submission.get("reported_test_coverage_percent", 88.0))
        reported_rt = float(submission.get("reported_response_time_ms", 150.0))
        min_cov = float(required.get("min_test_coverage_percent", 85.0))
        max_rt = float(required.get("max_response_time_ms", 200.0))
        lang = str(required.get("strict_language", "python"))

        cov_pass = reported_cov >= min_cov
        rt_pass = reported_rt <= max_rt
        scores = {
            "test_coverage": 100.0 if cov_pass else max(0, (reported_cov / min_cov) * 100),
            "response_time": 100.0 if rt_pass else max(0, (max_rt / reported_rt) * 100),
            "language_compliance": 95.0,
        }
        overall = sum(scores.values()) / len(scores)

        findings = []
        if cov_pass:
            findings.append(f"Test coverage {reported_cov}% meets minimum {min_cov}%")
        else:
            findings.append(f"Test coverage {reported_cov}% below minimum {min_cov}%")
        if rt_pass:
            findings.append(f"Response time {reported_rt}ms within {max_rt}ms budget")
        else:
            findings.append(f"Response time {reported_rt}ms exceeds {max_rt}ms limit")

        return {
            "test_coverage_percent": reported_cov,
            "response_time_ms": reported_rt,
            "language_detected": lang,
            "kpi_scores": scores,
            "overall_score_percent": round(overall, 2),
            "findings": findings,
        }

    def _mock_auditor_json(self, payload_text: str) -> dict[str, Any]:
        data = self._extract_json_payload(payload_text)
        if not data:
            try:
                data = json.loads(payload_text)
            except json.JSONDecodeError:
                data = {}

        validator = data.get("validator_output", data)
        overall = float(validator.get("overall_score_percent", 0))
        kpi_scores = validator.get("kpi_scores", {})
        approved = {k: v >= 80 for k, v in kpi_scores.items()}
        verdict = "Approved" if overall >= 80 and all(approved.values()) else "Rejected"
        summary = (
            f"Consensus reached: {verdict}. Overall KPI score {overall}%."
            if verdict == "Approved"
            else f"Consensus reached: {verdict}. KPI thresholds not fully met ({overall}%)."
        )
        audit_payload = json.dumps(validator, sort_keys=True)
        audit_hash = hashlib.sha256(audit_payload.encode()).hexdigest()

        return {
            "verdict": verdict,
            "consensus_score_percent": overall,
            "summary": summary,
            "approved_metrics": approved,
            "audit_hash": audit_hash,
        }

    async def fetch_oauth_userinfo(self, access_token: str) -> dict[str, Any]:
        """Fetch user profile from Chutes OAuth userinfo endpoint."""
        url = f"{self.settings.chutes_management_url.rstrip('/')}/idp/userinfo"
        client = await self._get_client()
        try:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise ChutesClientError(f"OAuth userinfo failed: {exc}") from exc

    async def exchange_oauth_code(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for tokens (Sign In with Chutes)."""
        url = f"{self.settings.chutes_management_url.rstrip('/')}/idp/token"
        client = await self._get_client()
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.chutes_oauth_redirect_uri,
            "client_id": self.settings.chutes_oauth_client_id,
            "client_secret": self.settings.chutes_oauth_client_secret,
        }
        try:
            response = await client.post(url, data=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise ChutesClientError(f"OAuth token exchange failed: {exc}") from exc


def inference_meta(response: dict[str, Any]) -> dict[str, Any]:
    """Extract whether a Chutes response was live or mock/fallback."""
    is_mock = bool(response.get("_mock"))
    return {
        "mode": "mock" if is_mock else "chutes_live",
        "mock": is_mock,
        "fallback_reason": response.get("_fallback_reason"),
        "inference_id": response.get("id"),
    }


def is_mock_inference_id(inference_id: str | None) -> bool:
    return bool(inference_id and inference_id.startswith("mock-chutes-"))


_chutes_client: ChutesClient | None = None


def get_chutes_client() -> ChutesClient:
    global _chutes_client
    if _chutes_client is None:
        _chutes_client = ChutesClient()
    return _chutes_client
