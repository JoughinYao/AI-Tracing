from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings


API_ENV = Path(__file__).resolve().parents[1] / ".env"
ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    app_name: str = "AI Tracing System API"
    api_host: str = "0.0.0.0"
    api_port: int = 8100
    database_url: str = "sqlite:///./ai_tracing.db"
    crawler_base_url: str = "http://127.0.0.1:8101"
    crawler_timeout_ms: int = 1200000
    frontend_origin: str = "http://localhost:5174"
    system_internal_token: str | None = None
    anthropic_api_url: str = "https://new-api.finstep.cn"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    # Legacy fallback for existing local .env files that still use OPENAI_* names.
    openai_api_key: str | None = None
    ranking_llm_enabled: bool = False
    ranking_llm_timeout_ms: int = 60000
    ranking_llm_max_retries: int = 2
    enable_scheduler: bool = True
    scheduler_timezone: str = "Asia/Shanghai"

    class Config:
        env_file = (str(ROOT_ENV), str(API_ENV))
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
