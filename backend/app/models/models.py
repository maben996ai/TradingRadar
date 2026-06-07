import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SourceType(StrEnum):
    BILIBILI = "bilibili"
    YOUTUBE = "youtube"
    TWITTER = "twitter"
    WECHAT_ARTICLE = "wechat_article"
    WEBSITE = "website"
    RSS = "rss"
    PDF = "pdf"


class ContentType(StrEnum):
    VIDEO = "video"
    ARTICLE = "article"
    NEWS = "news"
    MARKET = "market"


class CrawlLogStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


def uuid_str() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    data_sources: Mapped[list["DataSource"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    settings: Mapped["UserSettings | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    feishu_webhooks: Mapped[list["FeishuWebhook"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True)
    feishu_webhook_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="settings")


class DataSource(Base):
    __tablename__ = "data_sources"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "source_type", "external_id", name="uq_data_sources_user_type_external"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    source_type: Mapped[SourceType] = mapped_column(SqlEnum(SourceType, name="sourcetype"))
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    profile_url: Mapped[str] = mapped_column(Text())
    avatar_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content_type: Mapped[ContentType] = mapped_column(
        SqlEnum(ContentType, values_callable=lambda x: [e.value for e in x]),
        default=ContentType.VIDEO,
        server_default="video",
    )
    source_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    starred: Mapped[bool] = mapped_column(Boolean, default=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    initialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="data_sources")
    content_items: Mapped[list["ContentItem"]] = relationship(
        back_populates="data_source", cascade="all, delete-orphan"
    )
    crawl_logs: Mapped[list["CrawlLog"]] = relationship(
        back_populates="data_source", cascade="all, delete-orphan"
    )


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint(
            "data_source_id", "platform_id", name="uq_content_items_data_source_platform"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    data_source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_sources.id"), index=True
    )
    platform_id: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(500))
    thumbnail_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    content_url: Mapped[str] = mapped_column(Text())
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    data_source: Mapped[DataSource] = relationship(back_populates="content_items")


class FeishuWebhook(Base):
    __tablename__ = "feishu_webhooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    webhook_url: Mapped[str] = mapped_column(Text())
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="feishu_webhooks")


class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    data_source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_sources.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(50), default=CrawlLogStatus.SUCCESS)
    message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    items_found: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    data_source: Mapped[DataSource] = relationship(back_populates="crawl_logs")
