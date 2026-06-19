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
    # 内容分析（yt-dlp 下载 + Whisper 转写）
    content_analysis_dir: str = ""  # 产物落盘根目录，空则用 backend/data/content_analysis
    whisper_backend: str = "auto"  # auto | mlx | openai
    whisper_mlx_model: str = "mlx-community/whisper-large-v3-mlx"
    whisper_model: str = "base"  # openai-whisper 模型规格
    whisper_language: str = ""  # 空=自动检测
    content_analysis_auto_transcribe: bool = True  # 视频下载完成后自动转写
    content_analysis_delete_source_after_transcribe: bool = True  # 转写成功后删除源音/视频
    nginx_conf_file: str = "nginx.http.conf"
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_webhook_secret: str = ""
    frontend_base_url: str = ""  # 用于通知卡片中的详情链接
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
