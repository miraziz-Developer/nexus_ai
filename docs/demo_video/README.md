# Demo Video

Demo recordings are generated locally and are **not** committed to the repository (see root `.gitignore`).

## Generate

```bash
# Terminal 1
source .venv/bin/activate
uvicorn app.main:app --port 8000

# Terminal 2 — seed demo data, then record
python scripts/seed_professional_demo.py
python scripts/record_demo_video.py
```

Outputs (local only):

- `aether_nexus_demo.mp4` — main upload format (YouTube / Devpost)
- `aether_nexus_demo.srt` — subtitles for editors
- `frames/` — intermediate PNGs (safe to delete)

Demo accounts: `acme_corp` (company), `jane_dev` / `alex_freelancer` (freelancers).
