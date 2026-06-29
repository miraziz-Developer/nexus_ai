#!/usr/bin/env python3
"""Full end-to-end smoke test for Aether Nexus AI."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PASSED = 0
FAILED = 0


def ok(name: str, detail: str = "") -> None:
    global PASSED
    PASSED += 1
    print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))


def fail(name: str, detail: str = "") -> None:
    global FAILED
    FAILED += 1
    print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


def request(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def auth_user(chutes_id: str, role: str, name: str) -> dict:
    """Register new user or login if already exists."""
    data = json.dumps({
        "chutes_id": chutes_id, "role": role, "name": name,
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/api/v1/auth/register",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code != 409:
            raise
    return request("POST", "/api/v1/auth/login", body={"chutes_id": chutes_id})


def main() -> int:
    print("=" * 60)
    print("Aether Nexus AI — Full Smoke Test")
    print(f"Target: {BASE}")
    print("=" * 60)

    # 1. Health
    print("\n[1] Health & Chutes config")
    try:
        health = request("GET", "/health")
        if health.get("status") == "healthy":
            ok("GET /health", f"mode={health.get('chutes', {}).get('last_inference_mode', 'n/a')}")
        else:
            fail("GET /health", str(health))
    except Exception as exc:
        fail("GET /health", str(exc))
        print("\n❌ Server not running. Start with: uvicorn app.main:app --port 8000")
        return 1

    # 2. Auth
    print("\n[2] Authentication")
    try:
        co = auth_user("smoke_acme", "company", "Smoke Acme")
        fr = auth_user("smoke_jane", "freelancer", "Smoke Jane")
        co_token = co["access_token"]
        fr_token = fr["access_token"]
        ok("Company auth", co["user"]["chutes_id"])
        ok("Freelancer auth", fr["user"]["chutes_id"])
    except Exception as exc:
        fail("Auth", str(exc))
        return 1

    # 3. Contract + Agent 1
    print("\n[3] Contract creation (Agent 1 — Architect)")
    try:
        contract = request("POST", "/api/v1/contracts/create", co_token, {
            "raw_task_description": (
                "Build FastAPI backend with test coverage 85% and response under 200ms in Python"
            ),
            "freelancer_chutes_id": "smoke_jane",
            "budget_usd": 3000,
        })
        cid = contract["contract_id"]
        kpi = contract.get("kpi_blueprint", {})
        ok("POST /contracts/create", kpi.get("task_title", "")[:50])
        ok("KPI metrics", f"cov≥{kpi['required_metrics']['min_test_coverage_percent']}%")
        if contract.get("architect_inference_id"):
            ok("Architect inference_id", contract["architect_inference_id"][:24])
        else:
            fail("Architect inference_id missing")
    except Exception as exc:
        fail("Contract create", str(exc))
        return 1

    # 4. List contracts
    print("\n[4] Contract listing")
    try:
        listing = request("GET", "/api/v1/contracts/list", co_token)
        if listing["total"] >= 1:
            ok("Company list", f"{listing['total']} contract(s)")
        else:
            fail("Company list empty")
        flist = request("GET", "/api/v1/contracts/list", fr_token)
        if flist["total"] >= 1:
            ok("Freelancer list", f"{flist['total']} contract(s)")
        else:
            fail("Freelancer list empty")
    except Exception as exc:
        fail("Contract list", str(exc))

    # 5. Verification pipeline
    print("\n[5] Verification (Agents 2 + 3)")
    try:
        result = request("POST", "/api/v1/verify/submit", fr_token, {
            "contract_id": cid,
            "github_url": "https://github.com/tiangolo/fastapi",
            "reported_test_coverage_percent": 88,
            "reported_response_time_ms": 150,
            "notes": "Smoke test submission",
        })
        verdict = result.get("auditor_output", {}).get("verdict")
        score = result.get("auditor_output", {}).get("consensus_score_percent")
        payment = result.get("payment_recommendation_percent")
        if verdict == "Approved":
            ok("Consensus verdict", f"{verdict} @ {score}%")
        else:
            fail("Consensus verdict", verdict)
        ok("Payment recommendation", f"{payment}%")
        if result.get("on_chain_audit_id"):
            ok("On-chain audit_id", result["on_chain_audit_id"][:16])
        pipeline_len = len(result.get("agent_pipeline", []))
        ok("Agent pipeline steps", str(pipeline_len))
    except Exception as exc:
        fail("Verification", str(exc))
        return 1

    # 6. Status & graph
    print("\n[6] Audit tracking & charts")
    try:
        status = request("GET", f"/api/v1/verify/status/{cid}", co_token)
        ok("Verification status", status["status"])
        ok("Audit logs", f"{len(status.get('logs', []))} entries")
        ok("On-chain records", f"{len(status.get('on_chain_records', []))} record(s)")
        graph = request("GET", f"/api/v1/verify/consensus-graph/{cid}", co_token)
        if graph.get("scores") and max(graph["scores"]) > 0:
            ok("Consensus graph", str(graph["scores"]))
        else:
            fail("Consensus graph empty")
    except Exception as exc:
        fail("Audit tracking", str(exc))

    # 7. Static dashboard
    print("\n[7] Dashboard")
    try:
        req = urllib.request.Request(f"{BASE}/")
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode()
        if "Aether Nexus" in html and resp.status == 200:
            ok("Dashboard HTML", "loaded")
        else:
            fail("Dashboard HTML")
    except Exception as exc:
        fail("Dashboard", str(exc))

    # Summary
    print("\n" + "=" * 60)
    total = PASSED + FAILED
    print(f"Results: {PASSED}/{total} passed, {FAILED} failed")
    print("=" * 60)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
