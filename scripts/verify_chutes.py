#!/usr/bin/env python3
"""Verify Chutes decentralized inference connectivity."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.core.chutes_client import get_chutes_client
from app.core.config import get_settings


async def main() -> int:
    settings = get_settings()
    print("=" * 60)
    print("Aether Nexus AI — Chutes Connection Check")
    print("=" * 60)
    print(f"Inference URL : {settings.chutes_inference_url}")
    print(f"Model         : {settings.architect_model}")
    print(f"Has API key   : {settings.has_chutes_api_key}")
    print(f"Mock mode     : {settings.use_mock_inference}")
    print(f"Fallback      : {settings.allow_chutes_fallback}")
    print()

    if not settings.has_chutes_api_key:
        print("❌ No valid CHUTES_API_KEY in .env")
        print("   Get one at https://chutes.ai → API Keys (cpk_...)")
        return 1

    client = get_chutes_client()
    try:
        print("Sending test inference to Chutes network...")
        response = await client.chat_completion(
            model=settings.architect_model,
            messages=[
                {"role": "system", "content": "Reply with JSON only: {\"status\":\"ok\"}"},
                {"role": "user", "content": "ping"},
            ],
            response_format={"type": "json_object"},
            agent_name="verify",
        )
        inference_id = response.get("id", "unknown")
        mock = response.get("_mock", False)
        reason = response.get("_fallback_reason", "")
        content = response["choices"][0]["message"]["content"][:120]

        if not mock:
            print(f"✅ LIVE Chutes inference | id={inference_id}")
            print(f"   Response: {content}")
            return 0

        if reason.startswith("api_error") and settings.allow_chutes_fallback:
            print(f"⚠️  Chutes API key valid but live call failed ({reason})")
            print(f"   Fallback mock used | id={inference_id}")
            print("   → Top up balance at chutes.ai, then re-run this script.")
            print("   → App still works for demo via CHUTES_FALLBACK_ON_ERROR=true")
            return 0

        print(f"❌ Mock fallback active | reason={reason or 'unknown'}")
        return 1
    except Exception as exc:
        print(f"❌ Inference failed: {exc}")
        return 1
    finally:
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
