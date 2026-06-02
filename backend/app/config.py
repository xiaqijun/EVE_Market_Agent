from pydantic_settings import BaseSettings
import yaml
from pathlib import Path


class Settings(BaseSettings):
    esi_client_id: str = ""
    esi_client_secret: str = ""
    esi_callback_url: str = "http://localhost/api/v1/auth/eve/callback"
    esi_user_agent: str = "eve-market-agent/1.0 (+https://github.com/nicai0609/EVE_Market_Agent)"
    llm_orchestrator: str = "deepseek"
    llm_scanner: str = "deepseek"
    llm_analyst: str = "sonnet"
    llm_advisor: str = "opus"
    llm_memory: str = "deepseek"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    llm_monthly_budget_usd: float = 50.0
    rag_embedding_model: str = "local:all-MiniLM-L6-v2"
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

    # Market scan configuration
    scan_min_buy_price: float = 100000.0  # 最低买入价 (ISK)
    scan_min_sell_price: float = 100000.0  # 最低卖出价 (ISK)
    scan_min_profit_pct: float = 5.0  # 最低利润率 (%)
    scan_min_volume: int = 50  # 最小交易量
    scan_max_opportunities: int = 30  # 最大机会数
    scan_region_id: int = 10000002  # 默认扫描区域 (Forge)
    scan_regions: str = "10000002,10000043,10000032,10000042,10000030"  # 多区域列表

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
