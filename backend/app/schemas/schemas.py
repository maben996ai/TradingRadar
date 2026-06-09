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
    duration_seconds: int | None = None
    notified_at: datetime | None = None
    data_source_name: str
    data_source_avatar_url: str | None
    data_source_external_id: str
    source_type: SourceType


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
