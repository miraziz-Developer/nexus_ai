#!/usr/bin/env python3
"""Seed rich fake demo data for professional video (no Chutes API calls)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete

from app.core.db import get_session_factory, init_db
from app.models.orm import AuditLogRow, ContractRow, UserRow, VerificationLogRow


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _inf(prefix: str) -> str:
    return f"chutes-{prefix}-{uuid.uuid4().hex[:20]}"


def _kpi(title: str, cov: float, ms: float, lang: str) -> dict:
    return {
        "task_title": title,
        "required_metrics": {
            "min_test_coverage_percent": cov,
            "max_response_time_ms": ms,
            "strict_language": lang,
        },
        "milestones": [
            "Scaffold & CI setup",
            "Core implementation",
            f"Coverage ≥ {cov}%",
            f"Latency ≤ {ms}ms",
            "Documentation & handoff",
        ],
    }


def _validator_dump(score: float, cov: float, ms: float) -> dict:
    return {
        "test_coverage_percent": cov,
        "response_time_ms": ms,
        "language_detected": "python",
        "kpi_scores": {
            "test_coverage": min(100, score + 2),
            "response_time": score,
            "language_compliance": 95,
        },
        "overall_score_percent": score,
        "findings": [
            f"Test coverage {cov}% meets KPI threshold",
            f"Response time {ms}ms within budget",
            "GitHub repository structure verified",
        ],
        "inference_id": _inf("validator"),
        "inference_mode": "chutes_live",
    }


async def seed() -> None:
    await init_db()
    factory = get_session_factory()

    users = [
        ("acme_corp", "company", "Acme Corporation"),
        ("jane_dev", "freelancer", "Jane Dev"),
        ("alex_freelancer", "freelancer", "Alex Chen"),
    ]

    contracts_spec = [
        {
            "id": "demo-fastapi-001",
            "company": "acme_corp",
            "freelancer": "jane_dev",
            "status": "approved",
            "budget": 8500,
            "raw": "FastAPI backend with 85% test coverage and response under 200ms in Python",
            "kpi": _kpi("FastAPI Backend Development", 85, 200, "python"),
            "arch_inf": _inf("architect"),
            "verdict": "Approved",
            "score": 96.5,
            "val_score": 94,
            "cov": 88,
            "ms": 142,
        },
        {
            "id": "demo-react-002",
            "company": "acme_corp",
            "freelancer": "alex_freelancer",
            "status": "active",
            "budget": 4200,
            "raw": "React TypeScript analytics dashboard with 90% coverage and load time under 1.5s",
            "kpi": _kpi("React Analytics Dashboard", 90, 1500, "typescript"),
            "arch_inf": _inf("architect"),
            "verdict": None,
            "score": 0,
            "val_score": 0,
            "cov": 0,
            "ms": 0,
        },
        {
            "id": "demo-node-003",
            "company": "acme_corp",
            "freelancer": "jane_dev",
            "status": "rejected",
            "budget": 6000,
            "raw": "Node.js REST API migration with 80% coverage and p99 latency under 300ms",
            "kpi": _kpi("Node.js API Migration", 80, 300, "typescript"),
            "arch_inf": _inf("architect"),
            "verdict": "Rejected",
            "score": 62.0,
            "val_score": 58,
            "cov": 71,
            "ms": 380,
        },
    ]

    async with factory() as session:
        cids = [s["id"] for s in contracts_spec]
        await session.execute(delete(VerificationLogRow).where(VerificationLogRow.contract_id.in_(cids)))
        await session.execute(delete(AuditLogRow).where(AuditLogRow.contract_id.in_(cids)))
        await session.execute(delete(ContractRow).where(ContractRow.company_chutes_id == "acme_corp"))

        now = _utcnow()
        for chutes_id, role, name in users:
            row = await session.get(UserRow, chutes_id)
            if row is None:
                session.add(UserRow(chutes_id=chutes_id, role=role, name=name, created_at=now))
            else:
                row.name = name
                row.role = role

        for i, spec in enumerate(contracts_spec):
            created = now - timedelta(days=3 - i, hours=i * 2)
            validator = _validator_dump(spec["val_score"], spec["cov"], spec["ms"]) if spec["verdict"] else None
            auditor = None
            audit_hash = ""
            if spec["verdict"]:
                audit_hash = hashlib.sha256(json.dumps(validator, sort_keys=True).encode()).hexdigest()
                auditor = {
                    "verdict": spec["verdict"],
                    "consensus_score_percent": spec["score"],
                    "summary": (
                        f"Consensus reached: {spec['verdict']}. "
                        f"Overall KPI score {spec['score']}%."
                    ),
                    "approved_metrics": {
                        "test_coverage": spec["verdict"] == "Approved",
                        "response_time": spec["verdict"] == "Approved",
                        "language_compliance": True,
                    },
                    "audit_hash": audit_hash,
                    "inference_id": _inf("auditor"),
                    "inference_mode": "chutes_live",
                }

            last_ver = None
            if validator and auditor:
                last_ver = {
                    "validator": validator,
                    "auditor": auditor,
                    "audit_record_id": str(uuid.uuid4()),
                    "on_chain_audit_id": str(uuid.uuid4()),
                    "inference_summary": {"validator": "chutes_live", "auditor": "chutes_live"},
                }

            contract = ContractRow(
                contract_id=spec["id"],
                company_chutes_id=spec["company"],
                freelancer_chutes_id=spec["freelancer"],
                status=spec["status"],
                raw_task_description=spec["raw"],
                kpi_blueprint=spec["kpi"],
                budget_usd=spec["budget"],
                architect_inference_id=spec["arch_inf"],
                last_verification=last_ver,
                created_at=created,
                updated_at=now,
            )
            session.add(contract)
            await session.flush()

            logs = [
                ("system", "contract_created", "started", "Company submitted task requirements", None, None),
                ("architect", "kpi_generation", "completed",
                 f"KPI blueprint: {spec['kpi']['task_title']} [chutes_live]",
                 spec["arch_inf"], 100),
            ]
            if spec["verdict"]:
                logs += [
                    ("system", "submission_received", "completed", f"Freelancer {spec['freelancer']} submitted work", None, None),
                    ("validator", "artifact_validation", "completed",
                     f"Score: {spec['val_score']}%", validator["inference_id"], spec["val_score"]),
                    ("auditor", "consensus_review", "completed",
                     auditor["summary"], auditor["inference_id"], spec["score"]),
                ]
                session.add(AuditLogRow(
                    audit_id=str(uuid.uuid4()),
                    contract_id=spec["id"],
                    verdict=spec["verdict"],
                    consensus_score_percent=spec["score"],
                    audit_hash=audit_hash,
                    payload={
                        "contract_id": spec["id"],
                        "verdict": spec["verdict"],
                        "consensus_score_percent": spec["score"],
                        "audit_hash": audit_hash,
                        "auditor_summary": auditor["summary"],
                        "validator_output": validator,
                        "inference_ids": {
                            "architect": spec["arch_inf"],
                            "validator": validator["inference_id"],
                            "auditor": auditor["inference_id"],
                        },
                    },
                    network="chutes-decentralized-compute",
                    created_at=now - timedelta(hours=1),
                ))

            for agent, step, status, detail, inf_id, score in logs:
                session.add(VerificationLogRow(
                    log_id=str(uuid.uuid4()),
                    contract_id=spec["id"],
                    agent=agent,
                    step=step,
                    status=status,
                    detail=detail,
                    inference_id=inf_id,
                    score=score,
                    verdict=spec["verdict"] if agent == "auditor" else None,
                    created_at=created + timedelta(minutes=len(logs)),
                ))

        await session.commit()

    print("✅ Professional demo seeded:")
    print("   Users: acme_corp, jane_dev, alex_freelancer")
    print("   Contracts: 3 (approved, active, rejected)")
    print("   Audit logs + agent pipeline populated")


if __name__ == "__main__":
    asyncio.run(seed())
