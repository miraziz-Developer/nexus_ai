"""API integration tests (mock Chutes, in-memory SQLite)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["features"]["persistent_db"] is True


@pytest.mark.asyncio
async def test_register_and_login(client):
    reg = await client.post("/api/v1/auth/register", json={
        "chutes_id": "login_test_user", "role": "freelancer", "name": "Login Test",
    })
    assert reg.status_code == 201

    dup = await client.post("/api/v1/auth/register", json={
        "chutes_id": "login_test_user", "role": "freelancer", "name": "Login Test",
    })
    assert dup.status_code == 409

    login = await client.post("/api/v1/auth/login", json={"chutes_id": "login_test_user"})
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "freelancer"

    missing = await client.post("/api/v1/auth/login", json={"chutes_id": "no_such_user_xyz"})
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_full_pipeline(client):
    co = await client.post("/api/v1/auth/register", json={
        "chutes_id": "test_co", "role": "company", "name": "Test Co",
    })
    assert co.status_code == 201
    co_token = co.json()["access_token"]

    fr = await client.post("/api/v1/auth/register", json={
        "chutes_id": "test_fr", "role": "freelancer", "name": "Test FR",
    })
    fr_token = fr.json()["access_token"]

    contract = await client.post(
        "/api/v1/contracts/create",
        headers={"Authorization": f"Bearer {co_token}"},
        json={
            "raw_task_description": "FastAPI backend 85% coverage under 200ms Python",
            "freelancer_chutes_id": "test_fr",
            "budget_usd": 1000,
        },
    )
    assert contract.status_code == 201
    cid = contract.json()["contract_id"]
    assert contract.json()["kpi_blueprint"] is not None

    verify = await client.post(
        "/api/v1/verify/submit",
        headers={"Authorization": f"Bearer {fr_token}"},
        json={
            "contract_id": cid,
            "github_url": "https://github.com/tiangolo/fastapi",
            "reported_test_coverage_percent": 90,
            "reported_response_time_ms": 140,
        },
    )
    assert verify.status_code == 200
    result = verify.json()
    assert result["auditor_output"]["verdict"] in ("Approved", "Rejected")
    assert result["on_chain_audit_id"]

    status = await client.get(
        f"/api/v1/verify/status/{cid}",
        headers={"Authorization": f"Bearer {co_token}"},
    )
    assert status.status_code == 200
    assert len(status.json()["logs"]) >= 3
    assert len(status.json()["on_chain_records"]) >= 1


@pytest.mark.asyncio
async def test_persistence_after_new_client(client):
    """Data survives within same DB (list contracts)."""
    co = await client.post("/api/v1/auth/register", json={
        "chutes_id": "persist_co", "role": "company", "name": "Persist Co",
    })
    token = co.json()["access_token"]
    await client.post(
        "/api/v1/contracts/create",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "raw_task_description": "Python API with 80% test coverage and 300ms latency",
            "budget_usd": 500,
        },
    )
    listing = await client.get(
        "/api/v1/contracts/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listing.json()["total"] >= 1
