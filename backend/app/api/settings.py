from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import User, UserSettings
from app.schemas.schemas import SettingsResponse, SettingsUpdate
from app.services.notifiers.feishu import FeishuNotifier

router = APIRouter()
_notifier = FeishuNotifier()


async def get_or_create_user_settings(db: AsyncSession, user_id: str) -> UserSettings:
    settings = await db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if settings is None:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.get("/feishu", response_model=SettingsResponse)
async def get_feishu_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserSettings:
    settings = await get_or_create_user_settings(db, current_user.id)
    return settings


@router.put("/feishu", response_model=SettingsResponse)
async def update_feishu_settings(
    payload: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserSettings:
    settings = await get_or_create_user_settings(db, current_user.id)
    settings.feishu_webhook_url = payload.feishu_webhook_url
    await db.commit()
    await db.refresh(settings)
    return settings


@router.post("/feishu/test")
async def test_feishu_webhook(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = await get_or_create_user_settings(db, current_user.id)
    if not settings.feishu_webhook_url:
        return {"status": "error", "message": "未配置 Webhook 地址"}
    await _notifier.send_card(
        webhook_url=settings.feishu_webhook_url,
        title="TradingRader 通知测试 - 飞书推送已就绪",
        creator_name="测试创作者",
        platform="bilibili",
        content_url="https://www.bilibili.com",
        thumbnail_url="https://i0.hdslb.com/bfs/archive/d6e2b3ee64571c67ec534f39a3ab33380d2e0c4a.jpg",
        is_new_creator=False,
    )
    return {"status": "ok"}
