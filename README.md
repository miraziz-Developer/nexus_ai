# Aether Nexus AI

> **Decentralized autonomous escrow & multi-agent KPI verification engine**  
> Chutes Hack Malaysia 2026 · Corporate Track

[![Chutes](https://img.shields.io/badge/Powered%20by-Chutes%20AI-6366f1)](https://chutes.ai)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB)](https://python.org)

**Aether Nexus AI** (Nexus-Agent) is a trust layer between **Companies** and **Freelancers**. Companies write plain-English KPI requirements; three independent AI agents on the **Chutes decentralized compute network** convert them into strict JSON contracts, validate submitted work, and reach an immutable **Approved/Rejected** consensus — eliminating manual code review bottlenecks and payment disputes.

---

## The Problem

| Pain Point | Impact |
|------------|--------|
| **Time waste** | Senior engineers spend hours/days reviewing freelancer code and KPI compliance |
| **Trust disputes** | "I finished the work" vs "It doesn't meet our KPI standards" → delayed payments |
| **Manual escrow** | No automated, tamper-proof verification layer between parties |

## Our Solution

```
[Company]  →  writes task + KPI in plain English
     │
     ▼
[Agent 1: Architect]  →  Chutes inference  →  strict JSON KPI contract
     │
     ▼
[Freelancer]  →  submits GitHub repo / artifact + metrics
     │
     ▼
[Agent 2: Validator]  →  scores submission against KPIs
     │
     ▼
[Agent 3: Auditor]  →  multi-agent consensus  →  Approved/Rejected + immutable audit log
     │
     ▼
[Result]  →  automatic payment recommendation based on real KPI %
```

---

## Why This Wins (100-Point Rubric)

### 1. Multi-Agent Consensus Workflow — Chutes Compute (25 pts)

Unlike simple "one prompt → API wrapper" projects, we run **3 independent agent chains in parallel on Chutes**:

| Agent | Codename | Responsibility |
|-------|----------|----------------|
| **Agent 1** | The Legal/KPI Architect | Parses contract text → quantified JSON metrics (`min_test_coverage_percent`, `max_response_time_ms`, `strict_language`) |
| **Agent 2** | The Code/Artifact Validator | Audits freelancer submission (GitHub, coverage, latency) via Chutes inference |
| **Agent 3** | The Auditor/Consensus Agent | Compares Agent 1+2 outputs → final **Approved/Rejected** + cryptographic audit hash |

**Model:** `Qwen/Qwen3-32B-TEE` on `https://llm.chutes.ai/v1`

### 2. Deep Native Chutes Integration (25 pts)

| Feature | Implementation |
|---------|----------------|
| **Sign In with Chutes** | `POST /api/v1/auth/register` + `POST /api/v1/auth/login` (OAuth 2.0 PKCE hooks available) |
| **Chutes Inference** | Every KPI check logged with Chutes `inference_id` — tamper-evident audit trail |
| **Async Chutes Client** | `app/core/chutes_client.py` — full async/await HTTP engine to Chutes nodes |

### 3. Real Business Impact & Working MVP (25 pts)

- **FastAPI** — fully async, robust exception handling, structured logging
- **Role-based dual dashboard** — Company & Freelancer from one backend (`UserRole` enum)
- **Premium Horizon-inspired UI** — live consensus charts (ApexCharts), agent activity feed, verification audit view
- **Production-ready architecture** — modular agents, clean API versioning, `.env` configuration

---

## Quick Start

```bash
git clone https://github.com/miraziz-Developer/nexus_ai.git
cd nexus_ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Copy env and add your Chutes API key
cp .env.example .env
# Edit .env: CHUTES_API_KEY=cpk_... and MOCK_CHUTES_WHEN_NO_KEY=false

# 2. Verify real Chutes inference
python scripts/verify_chutes.py

# 3. Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Purpose |
|-----|---------|
| http://localhost:8000 | Dashboard (Company / Freelancer) |
| http://localhost:8000/docs | Swagger API |
| http://localhost:8000/health | Health check (`chutes_mock_mode` flag) |

---

## Demo Flow (3 minutes)

### Step 1 — Company creates a smart contract

1. Open dashboard → **Register** or **Sign In** as **Company**
   - Register once: `chutes_id`: `acme_corp` · `name`: `Acme Corp` · role: Company
   - Or sign in if already registered
2. **Create Smart Task** — example input:
   ```
   We need a FastAPI backend with test coverage ≥ 85% and API response time < 200ms in Python
   ```
3. **Agent 1 (Architect)** runs on Chutes → outputs JSON KPI blueprint with milestones

### Step 2 — Freelancer submits work

1. **Register** or **Sign In** as **Freelancer** (use incognito for a second session)
   - e.g. `chutes_id`: `jane_dev` · `name`: `Jane Dev`
2. Select active contract → submit GitHub URL + metrics:
   - Coverage: `88%` · Latency: `150ms`
3. **Agents 2 + 3** run consensus pipeline → e.g. **Approved @ 98.33%**

### Step 3 — Review audit trail

- **Agent Pipeline** tab — live step-by-step logs
- **Verification Audit** tab — verdict + SHA-256 audit hash

---

## API Reference

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/auth/register` | Any | Create account (Chutes ID + role) |
| `POST` | `/api/v1/auth/login` | Any | Sign in (existing Chutes ID) |
| `POST` | `/api/v1/auth/signin` | Any | Legacy alias for login |
| `GET` | `/api/v1/auth/oauth/authorize` | Any | OAuth authorization URL |
| `POST` | `/api/v1/auth/oauth/callback` | Any | OAuth code exchange |
| `POST` | `/api/v1/contracts/create` | Company | Create task → triggers Agent 1 |
| `GET` | `/api/v1/contracts/list` | Any | List contracts for role |
| `GET` | `/api/v1/contracts/{id}` | Any | Contract detail |
| `POST` | `/api/v1/verify/submit` | Freelancer | Submit work → Agents 2+3 |
| `GET` | `/api/v1/verify/status/{id}` | Any | Live audit logs |
| `GET` | `/api/v1/verify/consensus-graph/{id}` | Any | Chart data for dashboard |
| `GET` | `/health` | Public | Health + mock mode status |

---

## Project Structure

```
nexus_ai/
├── app/
│   ├── main.py                     # FastAPI entry, CORS, static dashboard
│   ├── api/v1/
│   │   ├── auth.py                 # Register / login / OAuth
│   │   ├── contracts.py            # Contract CRUD + Agent 1 trigger
│   │   └── verify.py               # Submission + Agents 2+3 pipeline
│   ├── core/
│   │   ├── chutes_client.py        # Async Chutes HTTP engine
│   │   ├── config.py               # Pydantic settings
│   │   ├── db.py                   # SQLite / PostgreSQL async engine
│   │   └── agents/
│   │       ├── architect.py        # Agent 1
│   │       ├── validator.py        # Agent 2
│   │       └── auditor.py          # Agent 3 + consensus
│   ├── repositories/store.py       # Persistence layer
│   ├── models/schemas.py           # Pydantic models & enums
│   └── static/                     # Horizon-inspired dashboard
├── scripts/
│   ├── verify_chutes.py            # Test real Chutes inference
│   ├── smoke_test.py               # E2E API checks
│   ├── live_audit.py               # Production honesty audit
│   ├── seed_professional_demo.py   # Demo data for recordings
│   └── record_demo_video.py        # Automated demo video (local output)
├── docs/
│   ├── screenshots/                # Devpost gallery (regenerate via script)
│   └── demo_video/                 # README only — videos stay local
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

---

## Configuration

```env
CHUTES_API_KEY=cpk_your_real_key_here
MOCK_CHUTES_WHEN_NO_KEY=false
CHUTES_FALLBACK_ON_ERROR=true    # demo works while balance is $0

ARCHITECT_MODEL=Qwen/Qwen3-32B-TEE
VALIDATOR_MODEL=Qwen/Qwen3-32B-TEE
AUDITOR_MODEL=Qwen/Qwen3-32B-TEE
```

List models available on your account:
```bash
curl -s -H "Authorization: Bearer $CHUTES_API_KEY" https://llm.chutes.ai/v1/models | python3 -m json.tool
```

### Run full test suite
```bash
uvicorn app.main:app --port 8000   # terminal 1
python scripts/smoke_test.py       # terminal 2 — expects 17/17 passed
python scripts/verify_chutes.py    # Chutes key + balance check
```

| Mode | `MOCK_CHUTES_WHEN_NO_KEY` | Behavior |
|------|---------------------------|----------|
| **Demo** | `true` | Local deterministic agent responses (no API key needed) |
| **Production / Judging** | `false` + valid `cpk_` key | Real Chutes decentralized inference |

Verify with:
```bash
python scripts/verify_chutes.py
# Expected: ✅ Inference OK | id=chutes-...  (NOT mock-chutes-...)
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, async/await, Pydantic v2 |
| AI Compute | Chutes decentralized network (`llm.chutes.ai/v1`) |
| Auth | Sign In with Chutes (OAuth 2.0 PKCE) |
| Frontend | Tailwind CSS, ApexCharts (Horizon UI inspired) |
| Data | SQLite by default (`data/nexus.db`) — PostgreSQL via `DATABASE_URL` |

---

## Real-World Scenario

> *"We need a FastAPI backend, test coverage ≥ 85%, API response < 200ms"*  
> → Agent 1 converts to JSON KPIs  
> → Freelancer submits GitHub repo  
> → Agent 2 runs tests & measures latency  
> → Agent 3: *"Coverage 88%, latency 150ms — **100% Approved**"*  
> → Cryptographic verification audit record — neither party can tamper with logged verdicts

---

## Image Gallery (Devpost)

Pre-captured screenshots (1920×1280, 3:2) in [`docs/screenshots/`](docs/screenshots/):

| Screenshot | Description |
|------------|-------------|
| `01-dashboard-overview.png` | Overview — ApexCharts consensus & radar |
| `02-company-create-contract.png` | Company creating smart task (Agent 1) |
| `03-agent-consensus-pipeline.png` | Multi-agent activity feed & consensus |
| `04-verification-audit-trail.png` | Verification audit records + SHA-256 hash |

Regenerate anytime:
```bash
MOCK_CHUTES_WHEN_NO_KEY=true uvicorn app.main:app --port 8000
python scripts/capture_screenshots.py
```

---

## Production Features (v1.0)

| Feature | Status |
|---------|--------|
| Persistent SQLite DB | Data survives restarts (`data/nexus.db`) |
| PostgreSQL ready | `DATABASE_URL=postgresql+asyncpg://...` |
| Live Chutes inference | 3-agent consensus on `Qwen/Qwen3-32B-TEE` |
| GitHub repo analysis | Agent 2 fetches real repo metadata |
| Docker deploy | `docker compose up --build` |
| pytest suite | `pytest -v` |
| Smoke test | `python scripts/smoke_test.py` (17 checks) |

```bash
docker compose up --build -d   # production deploy
pytest -v                      # unit/integration tests
python scripts/smoke_test.py   # full E2E
```

---

## Hackathon Submission Checklist

- [x] Multi-agent consensus on Chutes compute
- [x] Sign In with Chutes integration
- [x] Chutes inference audit logs
- [x] Working FastAPI MVP + dashboard
- [x] Persistent database
- [x] Live Chutes API + real inference IDs
- [ ] Record demo video + voiceover ([`docs/demo_video/README.md`](docs/demo_video/README.md))
- [ ] Submit GitHub + YouTube links on Devpost

> **Note:** Payment escrow and blockchain anchoring are not implemented in this MVP — see `GET /health` for feature flags.

---

## License

MIT — built for Chutes Hack Malaysia 2026.
