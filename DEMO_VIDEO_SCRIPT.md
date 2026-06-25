# 🎬 Demo Video Script — Aether Nexus AI (3–5 min)

Use **Loom** or **OBS**. Record at **1920×1080**, show browser + terminal side by side.

---

## 0:00 – 1:00 · The Problem

**[Screen: slide or dashboard login page]**

> "When companies hire freelancers, two things kill productivity:
>
> First — **time**. Senior engineers spend days manually reviewing code and checking if KPIs like test coverage or API latency were actually met.
>
> Second — **trust**. The freelancer says 'I'm done.' The company says 'It doesn't meet our standards.' Nobody wins, and payments get stuck.
>
> **Aether Nexus AI** solves this. We're a decentralized escrow and KPI verification engine powered by **Chutes** — three independent AI agents that act as an impartial judge between companies and freelancers."

---

## 1:00 – 2:30 · Live Dashboard Demo

**[Screen: http://localhost:8000]**

### Company flow (acme_corp)

1. Sign in:
   - Chutes ID: `acme_corp`
   - Name: `Acme Corp`
   - Role: **Company**

2. Go to **Contracts** → **Create Smart Task**

3. Paste this text:
   ```
   We need a FastAPI backend with test coverage at least 85% and API response time under 200ms in Python
   ```

4. Click **Generate KPI with Agent 1 (Architect)**

5. **Point out in UI:**
   - Agent 1 status changes to "completed"
   - JSON KPI appears: coverage ≥ 85%, latency ≤ 200ms, language: python
   - Show terminal logs: `[ARCHITECT] Chutes inference OK | id=...` (real ID, not `mock-chutes-`)

### Freelancer flow (jane_dev)

6. Open **incognito tab** → Sign in:
   - Chutes ID: `jane_dev`
   - Name: `Jane Dev`
   - Role: **Freelancer**

7. **Submit Work:**
   - Select the contract
   - GitHub URL: `https://github.com/tiangolo/fastapi` (or your repo)
   - Coverage: `88` · Latency: `150`
   - Click **Run Multi-Agent Verification**

8. **Show results:**
   - Agent 2 Validator: score ~98%
   - Agent 3 Auditor: **Approved**
   - Payment recommendation: **98.33%**
   - Switch to **Agent Pipeline** tab — live activity feed
   - Switch to **On-Chain Audit** — SHA-256 hash, immutable record

---

## 2:30 – 4:00 · Technical Depth

**[Screen: split — /docs left, VS Code right]**

### Swagger API (`/docs`)

Walk through 3 endpoints:
1. `POST /contracts/create` — triggers Agent 1
2. `POST /verify/submit` — chains Agents 2+3
3. `GET /verify/consensus-graph/{id}` — dashboard chart data

### Backend code (30 sec each)

1. **`app/core/chutes_client.py`**
   > "Async HTTP client to Chutes OpenAI-compatible endpoint. Bearer auth, JSON response format, inference IDs logged for audit."

2. **`app/core/agents/architect.py` → validator.py → auditor.py`**
   > "Three independent agents — not one wrapper. Architect structures KPIs, Validator scores submissions, Auditor reaches consensus and writes an immutable audit hash."

3. **Terminal:**
   ```bash
   python scripts/verify_chutes.py
   curl http://localhost:8000/health
   ```
   > Show `"chutes_mock_mode": false` and real inference ID.

---

## 4:00 – 4:30 · Closing

> "Aether Nexus AI — decentralized trust for the gig economy. Built on **Chutes** multi-agent consensus, **FastAPI** async backend, and a production-ready dashboard. GitHub link in description. Thank you!"

---

## Pre-recording checklist

```bash
# 1. Real Chutes key in .env
CHUTES_API_KEY=cpk_...
MOCK_CHUTES_WHEN_NO_KEY=false

# 2. Verify
python scripts/verify_chutes.py   # must show ✅ not mock

# 3. Start fresh server
uvicorn app.main:app --reload --port 8000

# 4. Clear browser localStorage (fresh demo)
# DevTools → Application → Local Storage → Clear
```

---

## Devpost submission fields

| Field | Value |
|-------|-------|
| **GitHub** | `https://github.com/miraziz-Developer/nexus_ai` |
| **YouTube** | *(your upload URL)* |
| **Tagline** | Decentralized multi-agent KPI escrow powered by Chutes |
| **Built with** | Chutes, FastAPI, Python, Tailwind CSS |
