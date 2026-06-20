from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.models import ContentType, CrawlLogStatus, SourceType


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DataSourceCreate(BaseModel):
    url: str
    note: str | None = None
    content_type: ContentType = ContentType.VIDEO
    source_config: dict | None = None


class DataSourceUpdate(BaseModel):
    note: str | None = None
    category: str | None = None
    starred: bool | None = None
    content_type: ContentType | None = None
    source_config: dict | None = None


class DataSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_type: SourceType
    external_id: str
    name: str
    profile_url: str
    avatar_url: str | None
    note: str | None
    category: str | None
    content_type: ContentType
    source_config: dict | None
    starred: bool
    notifications_enabled: bool
    initialized_at: datetime | None = None
    created_at: datetime


class QuotedContent(BaseModel):
    """被引用推文的精简内容（quote tweet 原帖）。"""

    text: str
    author_name: str
    author_username: str
    author_avatar_url: str | None = None
    thumbnail_url: str | None = None
    url: str | None = None


class ContentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    data_source_id: str
    platform_id: str
    title: str
    content_text: str
    thumbnail_url: str | None
    content_url: str
    published_at: datetime
    raw_data: dict | None = None
    quoted: QuotedContent | None = None
    duration_seconds: int | None = None
    notified_at: datetime | None = None
    data_source_name: str
    data_source_avatar_url: str | None
    data_source_external_id: str
    source_type: SourceType


class ResearchSource(BaseModel):
    key: str
    name: str


class ResearchResolveResponse(BaseModel):
    ticker: str
    company_name: str
    lookback_days: int


class ResearchItem(BaseModel):
    title: str
    url: str
    meta: str  # 日期等附注
    published_at: datetime | None = None


class ResearchSourceResult(BaseModel):
    items: list[ResearchItem]
    error: str | None = None


class SettingsUpdate(BaseModel):
    feishu_webhook_url: str | None = None


class SettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    feishu_webhook_url: str | None
    created_at: datetime
    updated_at: datetime


class ContentItemListResponse(BaseModel):
    items: list["ContentItemResponse"]
    next_cursor: str | None
    has_more: bool


class FeishuWebhookCreate(BaseModel):
    name: str
    webhook_url: str


class FeishuWebhookUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None


class FeishuWebhookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    webhook_url: str
    enabled: bool
    created_at: datetime


class MacroPoint(BaseModel):
    date: date
    value: float


class MacroIndicatorResponse(BaseModel):
    key: str
    category: str
    name: str
    name_en: str
    unit_label: str
    decimals: int
    source: str
    explanation: str
    latest: float
    previous: float | None
    change_abs: float | None
    change_pct: float | None
    updated_at: date
    judgment: Literal["bullish", "neutral", "bearish"]
    reason: str
    high: float | None
    low: float | None
    high_note: str
    low_note: str
    zone: Literal["high", "normal", "low"]
    forecast: float | None
    forecast_label: str | None
    forecast_source: str | None
    series: list[MacroPoint]


class MacroDashboardResponse(BaseModel):
    indicators: list[MacroIndicatorResponse]


class MacroRefreshResponse(BaseModel):
    inserted: int


class CalendarEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_key: str
    kind: str
    category: str
    title: str
    title_en: str
    country: str
    scheduled_at: datetime
    all_day: bool
    importance: int
    impact_assets: str | None
    previous: float | None
    forecast: float | None
    actual: float | None
    value_unit: str | None
    ticker: str | None
    company_name: str | None
    source: str


class CalendarEventListResponse(BaseModel):
    events: list[CalendarEventResponse]


class CalendarRefreshResponse(BaseModel):
    inserted: int


class TrackedTickerCreate(BaseModel):
    ticker: str
    company_name: str | None = None


class TrackedTickerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticker: str
    company_name: str | None
    created_at: datetime


class CrawlAcceptedResponse(BaseModel):
    status: CrawlLogStatus
    items_found: int


class CrawlLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    data_source_id: str
    status: CrawlLogStatus
    message: str | None
    items_found: int
    created_at: datetime


class FundamentalsSourceInfo(BaseModel):
    name: str


class FundamentalsDownloadRequest(BaseModel):
    ticker: str
    sources: list[str] | None = None


class FundamentalsArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    doc_type: str
    title: str
    file_path: str
    url: str | None = None
    period: str | None = None
    bytes_written: int


class FundamentalsSourceResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    skipped: bool
    message: str | None = None
    artifacts: list[FundamentalsArtifactResponse]


class FundamentalsDownloadResponse(BaseModel):
    ticker: str
    results: list[FundamentalsSourceResult]


# -- 内容分析（yt-dlp 下载 + Whisper 转写） --------------------------------


class AnalysisDownloadRequest(BaseModel):
    url: str
    mode: Literal["video", "audio"] = "video"


class AnalysisTranscribeRequest(BaseModel):
    pass


class AnalysisArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    stage: str
    status: str
    progress: float
    filename: str | None = None
    size: int | None = None
    error: str | None = None
    source_artifact_id: str | None = None
    meta: dict | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class AnalysisSourceResponse(BaseModel):
    id: str
    url: str
    title: str
    author: str | None = None
    created_at: datetime
    artifacts: list[AnalysisArtifactResponse]


class AnalysisListResponse(BaseModel):
    sources: list[AnalysisSourceResponse]
    counts: dict[str, int]


class AnalysisStatusResponse(BaseModel):
    transcribe_available: bool
    transcribe_backend: str
    youtube_logged_in: bool
    cookies_present: bool


class AnalysisLoginCookiesRequest(BaseModel):
    cookies: str


class AnalysisLoginBrowserRequest(BaseModel):
    browser: str
    profile: str | None = None


class AnalysisLoginResponse(BaseModel):
    ok: bool
    message: str


class AnalysisActionResponse(BaseModel):
    ok: bool
    message: str | None = None


class AnalysisProbeResponse(BaseModel):
    """cookies 活体探测结果三态。

    state: logged_in（已登录）/ logged_out（失效）/ inconclusive（无法判定）。
    """

    state: Literal["logged_in", "logged_out", "inconclusive"]
    ok: bool
    message: str | None = None


class AnalysisDeletedSourceResponse(BaseModel):
    """回收站条目：已软删除的来源。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    title: str
    author: str | None = None
    created_at: datetime
    deleted_at: datetime | None = None


class AnalysisFromContentItemRequest(BaseModel):
    mode: Literal["video", "audio"] = "video"
