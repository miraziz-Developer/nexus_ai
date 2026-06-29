#!/usr/bin/env python3
"""Production readiness audit — verifies REAL Chutes + GitHub + DB (not mock)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "✅" if ok else "❌"
    print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=15) as resp:
        return json.loads(resp.read())


def post(path: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def main() -> int:
    print("=" * 60)
    print("Aether Nexus — LIVE Production Audit")
    print(f"Target: {BASE}")
    print("=" * 60)

    # 1. Health honesty
    print("\n[1] Health & configuration")
    try:
        h = get("/health")
        c = h.get("chutes", {})
        f = h.get("features", {})
        check("Server healthy", h.get("status") == "healthy")
        check("Chutes API key configured", c.get("has_api_key"), "Set CHUTES_API_KEY=cpk_...")
        check("Mock mode OFF", not c.get("mock_mode"), "Set MOCK_CHUTES_WHEN_NO_KEY=false")
        check("Fallback OFF (production)", not c.get("fallback_on_error"), "Set CHUTES_FALLBACK_ON_ERROR=false")
        check("Payment escrow disclosed as false", f.get("payment_escrow") is False)
        check("Blockchain audit disclosed as false", f.get("blockchain_audit") is False)
        print(f"     honesty: {json.dumps(h.get('honesty', {}), indent=2)}")
    except Exception as exc:
        check("Health endpoint", False, str(exc))
        return 1

    # 2. Live Chutes inference
    print("\n[2] Live Chutes inference")
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "verify_chutes.py")],
        capture_output=True,
        text=True,
        cwd=str(root),
    )
    if result.stdout:
        print(result.stdout.rstrip())
    live_ok = result.returncode == 0 and "LIVE Chutes inference" in result.stdout
    check("Live Chutes inference", live_ok, "Run verify_chutes.py — need cpk_ key + balance")

    # 3. GitHub real API
    print("\n[3] GitHub metadata (real API)")
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/tiangolo/fastapi",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "AetherNexus-LiveAudit"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            gh = json.loads(resp.read())
        check("GitHub API reachable", bool(gh.get("full_name")), gh.get("full_name", ""))
        check("Language detected", bool(gh.get("language")), gh.get("language", ""))
    except Exception as exc:
        check("GitHub analysis", False, str(exc))

    # 4. Auth separation
    print("\n[4] Auth register/login separation")
    uid = f"live_audit_{__import__('uuid').uuid4().hex[:8]}"
    code, reg = post("/api/v1/auth/register", {"chutes_id": uid, "role": "company", "name": "Live Audit Co"})
    check("Register new user", code == 201, uid)
    code2, login = post("/api/v1/auth/login", {"chutes_id": uid})
    check("Login existing user", code2 == 200)
    code3, _dup = post("/api/v1/auth/register", {"chutes_id": uid, "role": "company", "name": "Dup"})
    check("Register duplicate rejected", code3 == 409)
    code4, _missing = post("/api/v1/auth/login", {"chutes_id": "nonexistent_user_xyz_999"})
    check("Login missing user rejected", code4 == 404)

    # 5. Protected users endpoint
    print("\n[5] Security")
    try:
        urllib.request.urlopen(f"{BASE}/api/v1/auth/users", timeout=10)
        check("GET /auth/users requires auth", False, "was publicly accessible")
    except urllib.error.HTTPError as exc:
        check("GET /auth/users requires auth", exc.code in (401, 403), f"HTTP {exc.code}")

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"❌ LIVE AUDIT FAILED ({len(FAILURES)} issues)")
        for f in FAILURES:
            print(f"   • {f}")
        return 1
    print("✅ LIVE AUDIT PASSED — production paths verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
