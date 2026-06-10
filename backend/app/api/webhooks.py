from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import FeishuWebhook, User
from app.schemas.schemas import FeishuWebhookCreate, FeishuWebhookResponse, FeishuWebhookUpdate
from app.services.notifiers.feishu import FeishuNotifier

router = APIRouter()
_notifier = FeishuNotifier()


async def _get_webhook_or_404(db: AsyncSession, webhook_id: str, user_id: str) -> FeishuWebhook:
    row = await db.scalar(
        select(FeishuWebhook).where(
            FeishuWebhook.id == webhook_id, FeishuWebhook.user_id == user_id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return row


@router.get("/feishu", response_model=list[FeishuWebhookResponse])
async def list_feishu_webhooks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FeishuWebhook]:
    rows = await db.scalars(select(FeishuWebhook).where(FeishuWebhook.user_id == current_user.id))
    return list(rows)


@router.post("/feishu", response_model=FeishuWebhookResponse, status_code=201)
async def create_feishu_webhook(
    payload: FeishuWebhookCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeishuWebhook:
    row = FeishuWebhook(user_id=current_user.id, name=payload.name, webhook_url=payload.webhook_url)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/feishu/{webhook_id}", response_model=FeishuWebhookResponse)
async def update_feishu_webhook(
    webhook_id: str,
    payload: FeishuWebhookUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeishuWebhook:
    row = await _get_webhook_or_404(db, webhook_id, current_user.id)
    if payload.name is not None:
        row.name = payload.name
    if payload.enabled is not None:
        row.enabled = payload.enabled
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/feishu/{webhook_id}", status_code=204)
async def delete_feishu_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await _get_webhook_or_404(db, webhook_id, current_user.id)
    await db.delete(row)
    await db.commit()


@router.post("/feishu/{webhook_id}/test")
async def test_feishu_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await _get_webhook_or_404(db, webhook_id, current_user.id)
    await _notifier.send_card(
        webhook_url=row.webhook_url,
        title="TradingRadar 通知测试 - 飞书推送已就绪",
        creator_name="测试创作者",
        platform="youtube",
        content_url="https://www.youtube.com/watch?v=test",
        thumbnail_url="https://i.ytimg.com/vi/test/hqdefault.jpg",
        is_new_creator=False,
    )
    return {"status": "ok"}
