#!/usr/bin/env python3
"""Capture Devpost gallery screenshots (3:2, 1920x1280). Requires server on :8000."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
VIEWPORT = {"width": 1920, "height": 1280}


def api(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def seed_via_api() -> tuple[str, dict, str]:
    co = api("POST", "/api/v1/auth/signin", body={
        "chutes_id": "acme_corp", "role": "company", "name": "Acme Corp",
    })
    fr = api("POST", "/api/v1/auth/signin", body={
        "chutes_id": "jane_dev", "role": "freelancer", "name": "Jane Dev",
    })
    contract = api("POST", "/api/v1/contracts/create", co["access_token"], {
        "raw_task_description": (
            "We need a FastAPI backend with test coverage at least 85% "
            "and API response time under 200ms in Python"
        ),
        "freelancer_chutes_id": "jane_dev",
        "budget_usd": 5000,
    })
    api("POST", "/api/v1/verify/submit", fr["access_token"], {
        "contract_id": contract["contract_id"],
        "github_url": "https://github.com/tiangolo/fastapi",
        "reported_test_coverage_percent": 88,
        "reported_response_time_ms": 150,
    })
    user = {"chutes_id": "acme_corp", "role": "company", "name": "Acme Corp", "email": None}
    return co["access_token"], user, contract["contract_id"]


def main() -> None:
    urllib.request.urlopen(f"{BASE}/health", timeout=5)
    OUT.mkdir(parents=True, exist_ok=True)

    token, user, contract_id = seed_via_api()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport=VIEWPORT)

        page.goto(BASE)
        page.evaluate(
            "([t,u]) => { localStorage.setItem('nexus_token',t); localStorage.setItem('nexus_user',JSON.stringify(u)); }",
            [token, user],
        )
        page.reload(wait_until="networkidle")
        time.sleep(2)

        def nav(view: str) -> None:
            page.click(f'button.nav-btn[data-view="{view}"]')
            time.sleep(1.5)

        # Load chart data for overview
        page.evaluate(f"fetch('/api/v1/verify/consensus-graph/{contract_id}', {{headers:{{Authorization:'Bearer {token}'}}}})")

        nav("overview")
        time.sleep(2.5)
        page.screenshot(path=str(OUT / "01-dashboard-overview.png"))

        nav("contracts")
        page.fill("#task-description",
            "We need a FastAPI backend with test coverage ≥ 85% and API response time < 200ms")
        page.fill("#freelancer-id", "jane_dev")
        page.fill("#budget", "5000")
        time.sleep(0.5)
        page.screenshot(path=str(OUT / "02-company-create-contract.png"))

        nav("agents")
        time.sleep(1)
        page.screenshot(path=str(OUT / "03-agent-consensus-pipeline.png"))

        nav("audit")
        time.sleep(1)
        page.screenshot(path=str(OUT / "04-onchain-audit-trail.png"))

        browser.close()

    print(f"✅ Screenshots → {OUT}")
    for f in sorted(OUT.glob("*.png")):
        print(f"   {f.name} ({f.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
