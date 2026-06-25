"""In-memory mock databases for hackathon MVP — swap for PostgreSQL in production."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


# chutes_id -> user record
users_db: dict[str, dict[str, Any]] = {}

# contract_id -> contract record
contracts_db: dict[str, dict[str, Any]] = {}

# contract_id -> list of verification log entries
verification_logs_db: dict[str, list[dict[str, Any]]] = {}

# session_token -> {chutes_id, created_at}
sessions_db: dict[str, dict[str, Any]] = {}

# on-chain style immutable audit trail (append-only)
on_chain_audit_db: list[dict[str, Any]] = []


def append_audit_log(entry: dict[str, Any]) -> dict[str, Any]:
    """Append an immutable on-chain style audit record."""
    record = {
        "audit_id": new_id(),
        "timestamp": _utcnow().isoformat(),
        "chain": "chutes-decentralized-compute",
        **entry,
    }
    on_chain_audit_db.append(record)
    return record


def append_verification_log(contract_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Append verification step log for a contract."""
    log_entry = {
        "log_id": new_id(),
        "timestamp": _utcnow().isoformat(),
        **entry,
    }
    verification_logs_db.setdefault(contract_id, []).append(log_entry)
    return log_entry
