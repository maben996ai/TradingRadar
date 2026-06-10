from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_SQLITE_PATH = ROOT_DIR / "backend" / "data" / "tradingradar.db"


class Settings(BaseSettings):
    app_name: str = "TradingRadar"
    api_prefix: str = "/api"
    database_url: str = f"sqlite+aiosqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 43200
    youtube_api_key: str = ""
    twitterapi_io_api_key: str = ""
    jin10_mcp_server_url: str = "https://mcp.jin10.com/mcp"
    jin10_mcp_bearer_token: str = ""
    jin10_mcp_protocol_version: str = "2025-11-25"
    fred_api_key: str = ""
    trading_economics_api_key: str = ""
    fmp_api_key: str = ""
    finnhub_api_key: str = ""
    quartr_api_key: str = ""
    sec_edgar_user_agent: str = ""
    fundamentals_dir: str = ""
    nginx_conf_file: str = "nginx.http.conf"
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    dev_account_email: str = "maben996@gmail.com"
    dev_account_display_name: str = "maben996"
    dev_account_password: str = ""

    model_config = SettingsConfigDict(
        env_file=str(ROOT_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
