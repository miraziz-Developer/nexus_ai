"""Aether Nexus AI — FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import auth, contracts, verify
from app.core.chutes_client import get_chutes_client
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aether.main")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting %s [%s]", settings.app_name, settings.app_env)
    logger.info(
        "Chutes inference: %s | mode=%s | fallback=%s",
        settings.chutes_inference_url,
        settings.inference_mode,
        settings.chutes_fallback_on_error,
    )
    yield
    await get_chutes_client().close()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Decentralized autonomous escrow and multi-agent KPI verification engine "
            "powered by Chutes decentralized compute."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_prefix = "/api/v1"
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(contracts.router, prefix=api_prefix)
    app.include_router(verify.router, prefix=api_prefix)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @app.get("/", include_in_schema=False)
        async def dashboard():
            return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    async def health():
        client = get_chutes_client()
        settings = get_settings()
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": "0.1.0",
            "chutes": {
                "inference_url": settings.chutes_inference_url,
                "has_api_key": settings.has_chutes_api_key,
                "mock_mode": settings.use_mock_inference,
                "fallback_on_error": settings.chutes_fallback_on_error,
                "last_inference_mode": client.last_inference_mode,
                "fallback_count": client.fallback_count,
                "architect_model": settings.architect_model,
            },
            "agents": ["architect", "validator", "auditor"],
        }

    return app


app = create_app()
