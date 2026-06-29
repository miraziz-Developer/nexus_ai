"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Aether Nexus AI"
    app_env: str = "development"
    secret_key: str = "dev-secret-key-change-in-production"
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    chutes_api_key: str = ""
    chutes_inference_url: str = "https://llm.chutes.ai/v1"
    chutes_management_url: str = "https://api.chutes.ai"

    chutes_oauth_client_id: str = ""
    chutes_oauth_client_secret: str = ""
    chutes_oauth_redirect_uri: str = "http://localhost:8000/api/v1/auth/oauth/callback"

    architect_model: str = "Qwen/Qwen3-32B-TEE"
    validator_model: str = "Qwen/Qwen3-32B-TEE"
    auditor_model: str = "Qwen/Qwen3-32B-TEE"

    mock_chutes_when_no_key: bool = False
    chutes_fallback_on_error: bool = False

    database_url: str = "sqlite+aiosqlite:///./data/nexus.db"
    github_token: str = ""
    db_echo: bool = False

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in ("development", "dev", "local")

    @property
    def allow_chutes_fallback(self) -> bool:
        """Fallback mock only when explicitly enabled (demo/dev)."""
        return self.chutes_fallback_on_error

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_chutes_api_key(self) -> bool:
        key = self.chutes_api_key.strip()
        return bool(key) and key.startswith("cpk_") and "your_api_key" not in key

    @property
    def use_mock_inference(self) -> bool:
        return self.mock_chutes_when_no_key and not self.has_chutes_api_key

    @property
    def inference_mode(self) -> str:
        if self.use_mock_inference:
            return "mock"
        return "chutes_live"


@lru_cache
def get_settings() -> Settings:
    return Settings()
