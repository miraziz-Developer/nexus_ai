#!/usr/bin/env python3
"""
Professional full demo video (~4–5 min) — company + freelancer, rich fake data.

  pip install playwright && playwright install chromium && brew install ffmpeg
  uvicorn app.main:app --port 8000

  python scripts/record_demo_video.py              # full professional (default)
  python scripts/record_demo_video.py --live       # real Chutes API calls (~8 min)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "demo_video"
FRAMES_DIR = OUT_DIR / "frames"
BASE = "http://127.0.0.1:8000"
VIEWPORT = {"width": 1920, "height": 1080}

TASK = (
    "We need a FastAPI backend with test coverage at least 85% "
    "and API response time under 200ms in Python"
)

_frame_plan: list[tuple[str, float, str]] = []  # path, hold, caption
_time_cursor: float = 0.0

OVERLAY_JS = """
() => {
  window.showDemoOverlay = (title, subtitle = '', badge = '') => {
    let el = document.getElementById('demo-recording-overlay');
    if (!el) {
      el = document.createElement('div');
      el.id = 'demo-recording-overlay';
      el.style.cssText = `
        position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;
        background:linear-gradient(135deg,rgba(7,5,26,0.97),rgba(15,13,46,0.97));
        font-family:DM Sans,system-ui,sans-serif;pointer-events:none;
      `;
      document.body.appendChild(el);
    }
    el.innerHTML = `
      <div style="text-align:center;max-width:720px;padding:2rem">
        ${badge ? `<p style="color:#818cf8;font-size:14px;letter-spacing:.2em;text-transform:uppercase;margin-bottom:1rem">${badge}</p>` : ''}
        <h1 style="font-size:3rem;font-weight:700;background:linear-gradient(135deg,#a5b4fc,#6366f1);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0 0 1rem">${title}</h1>
        ${subtitle ? `<p style="color:#9ca3af;font-size:1.25rem;line-height:1.6">${subtitle}</p>` : ''}
      </div>`;
    el.style.display = 'flex';
  };
  window.hideDemoOverlay = () => {
    const el = document.getElementById('demo-recording-overlay');
    if (el) el.style.display = 'none';
  };
  window.showGeneratingOverlay = () => {
    window.showDemoOverlay('Agent 1 Running…', 'Architect converting task → KPI contract on Chutes network', '🤖 Chutes Inference');
  };
  window.showVerifyingOverlay = () => {
    window.showDemoOverlay('Multi-Agent Verification', 'Validator + Auditor consensus on Chutes decentralized compute', '⚡ Agents 2 + 3');
  };
  window.showCaption = (text) => {
    if (!text) return;
    let el = document.getElementById('demo-caption-bar');
    if (!el) {
      el = document.createElement('div');
      el.id = 'demo-caption-bar';
      el.style.cssText = `
        position:fixed;bottom:0;left:0;right:0;z-index:10001;
        background:linear-gradient(to top,rgba(0,0,0,0.94) 65%,transparent);
        padding:18px 48px 30px;border-top:2px solid rgba(99,102,241,0.45);
        pointer-events:none;font-family:DM Sans,system-ui,sans-serif;
      `;
      document.body.appendChild(el);
    }
    const safe = String(text).replace(/&/g,'&amp;').replace(/</g,'&lt;');
    el.innerHTML = `
      <p style="margin:0;color:#818cf8;font-size:11px;letter-spacing:.12em;text-transform:uppercase;text-align:center">🎤 Read aloud</p>
      <p style="margin:10px auto 0;color:#f9fafb;font-size:22px;line-height:1.45;max-width:1280px;text-align:center;font-weight:500">${safe}</p>`;
    el.style.display = 'block';
  };
  window.hideCaption = () => {
    const el = document.getElementById('demo-caption-bar');
    if (el) el.style.display = 'none';
  };
}
"""


def api(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def login_api(chutes_id: str) -> tuple[str, dict]:
    data = api("POST", "/api/v1/auth/login", body={"chutes_id": chutes_id})
    return data["access_token"], data["user"]


def snap(page, label: str, hold: float = 6.0, caption: str = "") -> None:
    global _time_cursor
    inject_overlay(page)
    if caption:
        page.evaluate("(t) => showCaption(t)", caption)
    else:
        page.evaluate("() => hideCaption()")
    page.wait_for_timeout(400)
    idx = len(_frame_plan)
    path = FRAMES_DIR / f"{idx:04d}_{label}.png"
    page.screenshot(path=str(path), full_page=False, animations="disabled")
    _frame_plan.append((str(path), hold, caption))
    _time_cursor += hold
    print(f"    📸 {path.name} ({hold}s)")


def title_card(
    page,
    title: str,
    subtitle: str = "",
    badge: str = "",
    hold: float = 5.0,
    caption: str = "",
) -> None:
    inject_overlay(page)
    page.evaluate("([t,s,b]) => showDemoOverlay(t,s,b)", [title, subtitle, badge])
    snap(page, f"title_{label_slug(title)}", hold, caption=caption or subtitle)
    page.evaluate("() => hideDemoOverlay()")


def inject_overlay(page) -> None:
    page.evaluate(OVERLAY_JS)


def write_srt(path: Path) -> None:
    """Export karaoke captions as SRT for CapCut / YouTube."""
    t = 0.0

    def fmt(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, (_, hold, caption) in enumerate(_frame_plan, 1):
        if not caption:
            t += hold
            continue
        start, end = t, t + hold
        lines.append(str(i))
        lines.append(f"{fmt(start)} --> {fmt(end)}")
        lines.append(caption)
        lines.append("")
        t += hold
    path.write_text("\n".join(lines), encoding="utf-8")


def label_slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s[:30]).strip("_")


def type_slow(page, selector: str, text: str, delay_ms: int = 35) -> None:
    page.click(selector)
    page.fill(selector, "")
    page.type(selector, text, delay=delay_ms)


def session_login(page, token: str, user: dict) -> None:
    page.evaluate(
        "([t,u]) => { localStorage.setItem('nexus_token',t); localStorage.setItem('nexus_user',JSON.stringify(u)); }",
        [token, user],
    )
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_selector("#dashboard:not(.hidden)", timeout=15000)
    page.wait_for_timeout(1200)


def nav(page, view: str) -> None:
    page.click(f'button.nav-btn[data-view="{view}"]')
    page.wait_for_timeout(700)


def logout(page) -> None:
    try:
        page.evaluate("() => { if (typeof hideDemoOverlay === 'function') hideDemoOverlay(); }")
    except Exception:
        pass
    page.click("#logout-btn")
    page.wait_for_selector("#login-screen", timeout=10000)
    page.wait_for_timeout(600)


def click_contract(page, index: int = 0) -> None:
    cards = page.query_selector_all(".contract-card")
    if cards and index < len(cards):
        cards[index].click()
        page.wait_for_timeout(1500)


def run_seed() -> None:
    print("  🌱 Seeding professional demo data…")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_professional_demo.py")],
        check=True,
        cwd=str(ROOT),
    )


def record_professional(page) -> None:
    co_token, co_user = login_api("acme_corp")
    fr_token, fr_user = login_api("jane_dev")

    # ── INTRO ─────────────────────────────────────────────────────────────
    page.goto(BASE, wait_until="networkidle")
    title_card(
        page, "Aether Nexus AI",
        "Decentralized Multi-Agent KPI Verification · Chutes Hack Malaysia 2026",
        "⚡ Powered by Chutes", hold=6,
        caption=(
            "Hi judges — I'm presenting Aether Nexus AI for Chutes Hack Malaysia 2026. "
            "We automate KPI verification between companies and freelancers using three AI agents on Chutes."
        ),
    )
    snap(page, "01_login_screen", 7, caption=(
        "When companies hire freelancers, two things go wrong: manual code review takes days, "
        "and trust breaks down when KPIs aren't met. Aether Nexus fixes both with math and consensus."
    ))

    # ── COMPANY ───────────────────────────────────────────────────────────
    title_card(page, "Part 1 · Company", "Acme Corporation creates a smart KPI contract", "🏢 Client", hold=6,
               caption="Let me show you the live product. I'll start as a Company — Acme Corporation.")
    type_slow(page, "#login-chutes-id", "acme_corp", 60)
    snap(page, "02_company_login_typing", 5, caption="Sign in with your Chutes ID — companies and freelancers each get their own dashboard.")
    page.click("#login-btn")
    page.wait_for_selector("#dashboard", timeout=15000)
    page.wait_for_timeout(1500)
    snap(page, "03_company_dashboard_load", 4, caption="Welcome to the Company Dashboard — create smart tasks and track verification in real time.")

    session_login(page, co_token, co_user)
    nav(page, "overview")
    snap(page, "04_company_overview_stats", 10, caption=(
        "The overview shows active contracts, approved missions, agent inferences, and consensus scores — all in one place."
    ))

    nav(page, "contracts")
    snap(page, "05_contracts_list", 8, caption="Here are three contracts: approved, active, and rejected — each with measurable KPI badges.")
    click_contract(page, 0)
    snap(page, "06_contract_approved_detail", 8, caption=(
        "This FastAPI contract was approved at ninety-six percent — coverage eighty-five percent, latency under two hundred milliseconds."
    ))
    click_contract(page, 1)
    snap(page, "07_contract_active_detail", 6, caption="An active React dashboard mission waiting for the freelancer to submit work.")
    click_contract(page, 2)
    snap(page, "07b_contract_rejected", 7, caption="A rejected Node.js migration — consensus agents flagged KPIs that were not met.")

    page.fill("#task-description", "")
    page.fill("#freelancer-id", "")
    page.fill("#budget", "")
    type_slow(page, "#task-description", TASK, 25)
    snap(page, "08_typing_task", 5, caption="The company writes a task in plain English — no JSON, no technical setup required.")
    type_slow(page, "#freelancer-id", "jane_dev", 50)
    page.fill("#budget", "8500")
    snap(page, "09_form_ready", 7, caption="Assign a freelancer and budget, then trigger Agent 1 — the KPI Architect on Chutes.")

    inject_overlay(page)
    page.evaluate("() => showGeneratingOverlay()")
    snap(page, "10_agent1_generating", 10, caption=(
        "Agent 1 is running on Chutes decentralized compute — converting plain English into strict, measurable JSON KPIs."
    ))
    page.evaluate("() => hideDemoOverlay()")
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1500)
    nav(page, "contracts")
    snap(page, "11_contracts_after_kpi", 8, caption=(
        "Agent 1 returned structured KPIs: coverage minimum eighty-five percent, response under two hundred ms, Python stack."
    ))

    click_contract(page, 0)
    nav(page, "agents")
    page.wait_for_timeout(2000)
    snap(page, "12_agent_pipeline_activity", 12, caption=(
        "The Agent Pipeline shows all three agents — Architect, Validator, and Auditor — with live activity timestamps."
    ))

    nav(page, "audit")
    page.wait_for_timeout(1500)
    snap(page, "13_audit_trail", 10, caption=(
        "Every verification is logged with a SHA-256 audit hash — tamper-evident records linked to Chutes inference IDs."
    ))

    nav(page, "overview")
    page.wait_for_timeout(2500)
    snap(page, "14_charts_consensus", 10, caption="Consensus charts visualize agent scores across the full verification pipeline.")

    # ── FREELANCER ────────────────────────────────────────────────────────
    logout(page)
    title_card(page, "Part 2 · Freelancer", "Jane Dev submits work for multi-agent verification", "👨‍💻 Freelancer", hold=5,
               caption="Now let's switch to the Freelancer side — Jane Dev submits her completed work.")

    type_slow(page, "#login-chutes-id", "jane_dev", 60)
    page.click("#login-btn")
    page.wait_for_timeout(2000)
    session_login(page, fr_token, fr_user)

    nav(page, "contracts")
    snap(page, "15_freelancer_missions", 8, caption="Jane sees available missions and the Submit Work panel — select a contract and attach your GitHub repo.")

    page.select_option("#submit-contract-id", index=1)
    type_slow(page, "#github-url", "https://github.com/tiangolo/fastapi", 20)
    page.fill("#reported-coverage", "88")
    page.fill("#reported-latency", "142")
    page.fill("#artifact-notes", "All KPIs met. CI passing. Ready for consensus review.")
    snap(page, "16_submit_form_filled", 8, caption=(
        "She submits her GitHub URL, test coverage eighty-eight percent, and latency one-forty-two milliseconds."
    ))

    inject_overlay(page)
    page.evaluate("() => showVerifyingOverlay()")
    snap(page, "17_verifying", 12, caption=(
        "This triggers Agents 2 and 3 on Chutes — the Validator scores against KPIs, the Auditor reaches a final Approved or Rejected verdict."
    ))
    page.evaluate("() => hideDemoOverlay()")

    click_contract(page, 0)
    nav(page, "agents")
    page.wait_for_timeout(2000)
    snap(page, "18_freelancer_agents_done", 12, caption=(
        "Consensus reached: Approved. Validator scored the submission, Auditor confirmed with a cryptographic audit hash."
    ))

    nav(page, "audit")
    snap(page, "19_freelancer_audit", 10, caption=(
        "Real GitHub metadata enriches validation — language detection, test indicators, and CI workflows."
    ))

    nav(page, "overview")
    page.wait_for_timeout(2000)
    snap(page, "20_freelancer_overview", 8, caption="Both parties see the same immutable audit trail — no disputes, no manual review.")

    logout(page)
    title_card(page, "Aether Nexus AI", "3 Chutes Agents · GitHub Validation · Immutable Audit Trail", "✅ Consensus Verified", hold=8,
               caption="Aether Nexus AI — three Chutes agents, GitHub validation, and consensus-driven KPI verification. Thank you!")
    snap(page, "21_outro_login", 5, caption="Built for Chutes Hack Malaysia 2026. GitHub: miraziz-Developer/nexus_ai")


def record_live(page) -> None:
    """Real Chutes inference — slow but authentic."""
    page.goto(BASE, wait_until="networkidle")
    title_card(page, "Aether Nexus AI", "Live Chutes Inference Demo", "🔴 LIVE", hold=5)

    page.click("#tab-register")
    page.fill("#register-chutes-id", "acme_corp")
    page.fill("#register-name", "Acme Corp")
    page.select_option("#register-role", "company")
    try:
        page.click("#register-btn")
        page.wait_for_selector("#dashboard", timeout=15000)
    except Exception:
        page.click("#tab-login")
        page.fill("#login-chutes-id", "acme_corp")
        page.click("#login-btn")
        page.wait_for_selector("#dashboard", timeout=15000)

    nav(page, "contracts")
    type_slow(page, "#task-description", TASK, 20)
    page.fill("#freelancer-id", "jane_dev")
    page.fill("#budget", "5000")
    snap(page, "live_form", 3)
    page.click("#create-contract-btn")
    snap(page, "live_agent1", 4)
    page.wait_for_selector("#create-contract-loading", state="hidden", timeout=300000)
    snap(page, "live_kpi_done", 5)

    logout(page)
    page.click("#tab-register")
    page.fill("#register-chutes-id", "jane_dev")
    page.fill("#register-name", "Jane Dev")
    page.select_option("#register-role", "freelancer")
    try:
        page.click("#register-btn")
        page.wait_for_selector("#dashboard", timeout=15000)
    except Exception:
        page.click("#tab-login")
        page.fill("#login-chutes-id", "jane_dev")
        page.click("#login-btn")

    nav(page, "contracts")
    page.select_option("#submit-contract-id", index=1)
    page.fill("#github-url", "https://github.com/tiangolo/fastapi")
    page.fill("#reported-coverage", "88")
    page.fill("#reported-latency", "150")
    page.click('#submit-work-form button[type="submit"]')
    snap(page, "live_verify", 5)
    try:
        page.wait_for_function(
            "() => (document.getElementById('agent3-status')?.textContent || '').match(/Approved|Rejected/)",
            timeout=300000,
        )
    except Exception:
        page.wait_for_timeout(45000)
    nav(page, "agents")
    snap(page, "live_result", 6)
    nav(page, "audit")
    snap(page, "live_audit", 6)


def build_video(output: Path) -> None:
    list_file = FRAMES_DIR / "concat.txt"
    with list_file.open("w") as f:
        for path, dur, _caption in _frame_plan:
            f.write(f"file '{Path(path).name}'\n")
            f.write(f"duration {dur}\n")
        if _frame_plan:
            f.write(f"file '{Path(_frame_plan[-1][0]).name}'\n")

    mp4 = output.with_suffix(".mp4")
    webm = output.with_suffix(".webm")
    for out, extra in ((mp4, ["-crf", "20"]), (webm, ["-b:v", "3M"])):
        vcodec = "libx264" if out.suffix == ".mp4" else "libvpx-vp9"
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
            "-vf", "scale=1920:1080:flags=lanczos,format=yuv420p",
            "-c:v", vcodec, "-pix_fmt", "yuv420p", *extra, str(out.resolve()),
        ]
        result = subprocess.run(cmd, cwd=str(FRAMES_DIR), capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr[-1000:])
            raise subprocess.CalledProcessError(result.returncode, cmd)
    print(f"    🎬 {mp4.name} ({mp4.stat().st_size // 1024 // 1024} MB)")


def main() -> int:
    global _frame_plan, _time_cursor
    parser = argparse.ArgumentParser(description="Record professional Aether Nexus demo")
    parser.add_argument("--live", action="store_true", help="Real Chutes API (slow)")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--no-seed", action="store_true", help="Skip DB seed (pro mode only)")
    args = parser.parse_args()

    try:
        urllib.request.urlopen(f"{BASE}/health", timeout=5)
    except Exception as exc:
        print(f"❌ Server not running: {exc}")
        return 1

    from playwright.sync_api import sync_playwright

    if not args.live and not args.no_seed:
        run_seed()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for f in FRAMES_DIR.glob("*.png"):
        f.unlink()
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    _frame_plan = []
    _time_cursor = 0.0

    mode = "LIVE Chutes" if args.live else "PROFESSIONAL (rich demo data)"
    print("=" * 60)
    print(f"Aether Nexus — Full Demo Video · {mode}")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(viewport=VIEWPORT, color_scheme="dark")
        page = context.new_page()
        page.add_init_script(OVERLAY_JS)
        page.set_default_timeout(300000)

        if args.live:
            record_live(page)
        else:
            record_professional(page)
        browser.close()

    print(f"\nBuilding video from {len(_frame_plan)} frames…")
    build_video(OUT_DIR / "aether_nexus_demo")
    srt_path = OUT_DIR / "aether_nexus_demo.srt"
    write_srt(srt_path)
    total = sum(d for _, d, _ in _frame_plan)
    mins = int(total // 60)
    secs = int(total % 60)
    print(f"\n✅ Done — ~{mins}m {secs}s")
    print(f"   MP4:  {OUT_DIR / 'aether_nexus_demo.mp4'}")
    print(f"   SRT:  {srt_path}  (CapCut / YouTube subtitles)")
    print("   Subtitles are burned into the video — read the bottom bar while presenting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
