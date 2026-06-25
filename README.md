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
[Agent 1: Architect]  →  Chutes on-chain inference  →  strict JSON KPI contract
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
| **Agent 2** | The Code/Artifact Validator | Audits freelancer submission (GitHub, coverage, latency) via on-chain inference |
| **Agent 3** | The Auditor/Consensus Agent | Compares Agent 1+2 outputs → final **Approved/Rejected** + cryptographic audit hash |

**Model:** `meta-llama/Meta-Llama-3-70B-Instruct` on `https://llm.chutes.ai/v1`

### 2. Deep Native Chutes Integration (25 pts)

| Feature | Implementation |
|---------|----------------|
| **Sign In with Chutes** | `POST /api/v1/auth/signin` (demo) + OAuth 2.0 PKCE hooks (`/auth/oauth/authorize`, `/auth/oauth/callback`) |
| **On-Chain Inference** | Every KPI check logged with Chutes `inference_id` — tamper-proof audit trail |
| **Async Chutes Client** | `app/core/chutes_client.py` — full async/await HTTP engine to Chutes nodes |

### 3. Real Business Impact & Working MVP (25 pts)

- **FastAPI** — fully async, robust exception handling, structured logging
- **Role-based dual dashboard** — Company & Freelancer from one backend (`UserRole` enum)
- **Premium Horizon-inspired UI** — live consensus charts (ApexCharts), agent activity feed, on-chain audit view
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

1. Open dashboard → Sign in as **Company**
   - `chutes_id`: `acme_corp` · `name`: `Acme Corp`
2. **Create Smart Task** — example input:
   ```
   We need a FastAPI backend with test coverage ≥ 85% and API response time < 200ms in Python
   ```
3. **Agent 1 (Architect)** runs on Chutes → outputs JSON KPI blueprint with milestones

### Step 2 — Freelancer submits work

1. Sign in as **Freelancer** (incognito tab)
   - `chutes_id`: `jane_dev` · `name`: `Jane Dev`
2. Select active contract → submit GitHub URL + metrics:
   - Coverage: `88%` · Latency: `150ms`
3. **Agents 2 + 3** run consensus pipeline → e.g. **Approved @ 98.33%**

### Step 3 — Review audit trail

- **Agent Pipeline** tab — live step-by-step logs
- **On-Chain Audit** tab — immutable verdict + SHA-256 audit hash

---

## API Reference

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/auth/signin` | Any | Sign In with Chutes (session token) |
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
│   │   ├── auth.py                 # Sign In with Chutes
│   │   ├── contracts.py            # Contract CRUD + Agent 1 trigger
│   │   └── verify.py               # Submission + Agents 2+3 pipeline
│   ├── core/
│   │   ├── chutes_client.py        # Async Chutes HTTP engine
│   │   ├── config.py               # Pydantic settings
│   │   ├── database.py             # In-memory stores (MVP)
│   │   └── agents/
│   │       ├── architect.py        # Agent 1
│   │       ├── validator.py        # Agent 2
│   │       └── auditor.py          # Agent 3 + consensus
│   ├── models/schemas.py           # Pydantic models & enums
│   └── static/                     # Horizon-inspired dashboard
├── scripts/
│   └── verify_chutes.py            # Test real Chutes inference
├── .env.example
├── requirements.txt
└── README.md
```

---

## Configuration

```env
CHUTES_API_KEY=cpk_your_real_key_here          # Required for judging
CHUTES_INFERENCE_URL=https://llm.chutes.ai/v1
MOCK_CHUTES_WHEN_NO_KEY=false                  # Must be false for real inference

ARCHITECT_MODEL=meta-llama/Meta-Llama-3-70B-Instruct
VALIDATOR_MODEL=meta-llama/Meta-Llama-3-70B-Instruct
AUDITOR_MODEL=meta-llama/Meta-Llama-3-70B-Instruct
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
| Data (MVP) | In-memory dict stores — swap for PostgreSQL in production |

---

## Real-World Scenario

> *"We need a FastAPI backend, test coverage ≥ 85%, API response < 200ms"*  
> → Agent 1 converts to JSON KPIs  
> → Freelancer submits GitHub repo  
> → Agent 2 runs tests & measures latency  
> → Agent 3: *"Coverage 88%, latency 150ms — **100% Approved**"*  
> → Immutable on-chain audit record — neither party can tamper

---

## Image Gallery (Devpost)

Pre-captured screenshots (1920×1280, 3:2) in [`docs/screenshots/`](docs/screenshots/):

| Screenshot | Description |
|------------|-------------|
| `01-dashboard-overview.png` | Overview — ApexCharts consensus & radar |
| `02-company-create-contract.png` | Company creating smart task (Agent 1) |
| `03-agent-consensus-pipeline.png` | Multi-agent activity feed & consensus |
| `04-onchain-audit-trail.png` | Immutable on-chain audit records |

Regenerate anytime:
```bash
MOCK_CHUTES_WHEN_NO_KEY=true uvicorn app.main:app --port 8000
python scripts/capture_screenshots.py
```

---

- [x] Multi-agent consensus on Chutes compute
- [x] Sign In with Chutes integration
- [x] On-chain inference audit logs
- [x] Working FastAPI MVP + dashboard
- [ ] Set `CHUTES_API_KEY` in `.env` + `MOCK_CHUTES_WHEN_NO_KEY=false`
- [ ] Run `python scripts/verify_chutes.py` — confirm real inference IDs
- [ ] Record 3–5 min demo video (see `DEMO_VIDEO_SCRIPT.md`)
- [ ] Submit GitHub + YouTube links on Devpost

---

## License

MIT — built for Chutes Hack Malaysia 2026.
