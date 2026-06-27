"""GitHub repository analysis for Agent 2 validation."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

logger = logging.getLogger("aether.github")

_GH_RE = re.compile(r"github\.com[/:](?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)")


def parse_github_url(url: str | None) -> tuple[str, str] | None:
    if not url:
        return None
    match = _GH_RE.search(url)
    if not match:
        return None
    repo = match.group("repo").removesuffix(".git")
    return match.group("owner"), repo


async def analyze_repository(github_url: str | None) -> dict[str, Any]:
    """
    Fetch public GitHub metadata to enrich validator context.
    Uses GITHUB_TOKEN if set (higher rate limits).
    """
    parsed = parse_github_url(github_url)
    if not parsed:
        return {"available": False, "reason": "invalid_or_missing_github_url"}

    owner, repo = parsed
    settings = get_settings()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    api = f"https://api.github.com/repos/{owner}/{repo}"
    logger.info("[GITHUB] Analyzing %s/%s", owner, repo)

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(api, headers=headers)
            if resp.status_code == 404:
                return {"available": False, "reason": "repository_not_found", "owner": owner, "repo": repo}
            resp.raise_for_status()
            data = resp.json()

            languages_resp = await client.get(f"{api}/languages", headers=headers)
            languages = languages_resp.json() if languages_resp.status_code == 200 else {}

            # Check for test indicators in root contents
            has_tests = False
            contents_resp = await client.get(f"{api}/contents", headers=headers)
            if contents_resp.status_code == 200:
                names = {item.get("name", "").lower() for item in contents_resp.json()}
                has_tests = bool(
                    names & {"tests", "test", "pytest.ini", "pyproject.toml", ".github"}
                )

        primary_language = data.get("language") or (max(languages, key=languages.get) if languages else None)
        stars = data.get("stargazers_count", 0)
        open_issues = data.get("open_issues_count", 0)

        analysis = {
            "available": True,
            "owner": owner,
            "repo": repo,
            "full_name": data.get("full_name"),
            "description": data.get("description"),
            "primary_language": primary_language,
            "languages": languages,
            "stars": stars,
            "open_issues": open_issues,
            "has_test_indicators": has_tests,
            "default_branch": data.get("default_branch"),
            "updated_at": data.get("updated_at"),
            "html_url": data.get("html_url"),
        }
        logger.info("[GITHUB] Analysis OK | lang=%s stars=%s", primary_language, stars)
        return analysis
    except httpx.HTTPError as exc:
        logger.warning("[GITHUB] Analysis failed: %s", exc)
        return {"available": False, "reason": str(exc), "owner": owner, "repo": repo}
