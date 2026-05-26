from pydantic_settings import BaseSettings
import yaml
from pathlib import Path


class Settings(BaseSettings):
    esi_client_id: str = ""
    esi_client_secret: str = ""
    esi_callback_url: str = "http://localhost/api/v1/auth/eve/callback"
    esi_user_agent: str = "eve-market-agent/1.0"
    llm_orchestrator: str = "deepseek"
    llm_scanner: str = "deepseek"
    llm_analyst: str = "sonnet"
    llm_advisor: str = "opus"
    llm_memory: str = "deepseek"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    llm_monthly_budget_usd: float = 50.0
    rag_embedding_model: str = "openai:text-embedding-3-small"
    rag_reranker_model: str = "none"
    rag_top_k: int = 5
    postgres_host: str = "postgres"
    postgres_db: str = "eve_market"
    postgres_user: str = "eve_market"
    postgres_password: str = "change-me-in-production"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = "change-me-in-production"
    encryption_key: str = "change-me-in-production-change-me"
    smtp_host: str = ""
    discord_webhook_url: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:5432/{self.postgres_db}"
        )

    def load_model_config(self) -> dict:
        path = Path(__file__).parent.parent.parent / "models.yaml"
        if not path.exists():
            path = Path("models.yaml")
        with open(path) as f:
            return yaml.safe_load(f)

    class Config:
        env_file = ".env"


settings = Settings()
