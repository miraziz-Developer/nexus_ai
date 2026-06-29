# Image Gallery — Devpost Screenshots

Upload these PNG files to your Devpost **Image Gallery** (3:2 ratio, 1920×1280).

| File | Description | Devpost caption |
|------|-------------|-----------------|
| `01-dashboard-overview.png` | Overview with ApexCharts consensus + radar | *Aether Nexus dashboard — live KPI analytics* |
| `02-company-create-contract.png` | Company creating smart task (Agent 1) | *Company creates plain-English task → Agent 1 generates JSON KPIs* |
| `03-agent-consensus-pipeline.png` | Multi-agent activity feed | *Agents 2+3 consensus pipeline on Chutes compute* |
| `04-verification-audit-trail.png` | Verification audit records | *Tamper-evident audit trail with SHA-256 hash* |

## Regenerate screenshots

```bash
# Terminal 1
uvicorn app.main:app --port 8000

# Terminal 2
pip install playwright
playwright install chromium
python scripts/capture_screenshots.py
```

## Manual capture (macOS)

1. Open http://localhost:8000
2. `Cmd + Shift + 4` → drag to capture window
3. Or Chrome DevTools → `Cmd + Shift + P` → "Capture screenshot"

Recommended browser width: **1920px** for 3:2 ratio.
