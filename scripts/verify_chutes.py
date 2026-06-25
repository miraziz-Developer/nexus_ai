#!/usr/bin/env python3
"""Verify real Chutes decentralized inference is working."""

from __future__ import annotations

import asyncio
import os
import sys

# Load .env before app imports
from dotenv import load_dotenv

load_dotenv()

from app.core.config import get_settings
from app.core.chutes_client import get_chutes_client


async def main() -> int:
    settings = get_settings()
    print("=" * 60)
    print("Aether Nexus AI — Chutes Connection Check")
    print("=" * 60)
    print(f"Inference URL : {settings.chutes_inference_url}")
    print(f"Model         : {settings.architect_model}")
    print(f"Has API key   : {settings.has_chutes_api_key}")
    print(f"Mock mode     : {settings.use_mock_inference}")
    print()

    if not settings.has_chutes_api_key:
        print("❌ No valid CHUTES_API_KEY in .env")
        print("   Get one at https://chutes.ai → API Keys (cpk_...)")
        print("   Then set MOCK_CHUTES_WHEN_NO_KEY=false")
        return 1

    if settings.use_mock_inference:
        print("❌ MOCK_CHUTES_WHEN_NO_KEY is still true")
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
        content = response["choices"][0]["message"]["content"][:120]
        print(f"✅ Inference OK | id={inference_id}")
        print(f"   Mock fallback: {mock}")
        print(f"   Response preview: {content}")
        return 0 if not mock else 1
    except Exception as exc:
        print(f"❌ Inference failed: {exc}")
        return 1
    finally:
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
