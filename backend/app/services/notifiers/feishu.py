import logging
from datetime import datetime

import httpx

from app.services.notifiers.base import BaseNotifier
from app.services.notifiers.feishu_client import FeishuAppClient, get_feishu_app_client

logger = logging.getLogger(__name__)


def _format_published_at(dt: datetime) -> str:
    """与前端 formatPublishedAt 规则保持一致：分秒都为 0 时降级为小时级。"""
    if dt.minute == 0 and dt.second == 0:
        return dt.strftime("%Y-%m-%d %H:00:00")
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class FeishuNotifier(BaseNotifier):
    def __init__(self, app_client: FeishuAppClient | None = None) -> None:
        self._app_client = app_client or get_feishu_app_client()

    async def send(self, message: str, webhook_url: str) -> None:
        if not webhook_url:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                webhook_url,
                json={"msg_type": "text", "content": {"text": message}},
            )

    async def _resolve_image_key(self, thumbnail_url: str | None) -> str | None:
        if not thumbnail_url or not self._app_client.configured:
            return None
        try:
            return await self._app_client.upload_image_from_url(thumbnail_url)
        except Exception as exc:
            logger.warning("Feishu image upload failed, fall back to text link: %s", exc)
            return None

    async def send_card(
        self,
        webhook_url: str,
        title: str,
        creator_name: str,
        platform: str,
        content_url: str,
        thumbnail_url: str | None = None,
        published_at: datetime | None = None,
        is_new_creator: bool = False,
    ) -> None:
        if not webhook_url:
            return

        header_title = (
            f"🆕 新增信源：{creator_name}" if is_new_creator else f"📹 新视频：{creator_name}"
        )
        platform_label = "X" if platform == "twitter" else "YouTube"

        image_key = await self._resolve_image_key(thumbnail_url)

        title_md = f"**[{title}]({content_url})**"
        if thumbnail_url and not image_key:
            # 自建应用未配置 or 上传失败时回退为链接
            title_md += f"\n\n🖼 [封面预览]({thumbnail_url})"

        fields = [
            {
                "is_short": True,
                "text": {"tag": "lark_md", "content": f"**平台**\n{platform_label}"},
            },
            {
                "is_short": True,
                "text": {"tag": "lark_md", "content": f"**创作者**\n{creator_name}"},
            },
        ]
        if published_at is not None:
            fields.append(
                {
                    "is_short": False,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**发布时间**\n{_format_published_at(published_at)}",
                    },
                }
            )

        elements: list[dict] = []
        if image_key:
            elements.append(
                {
                    "tag": "img",
                    "img_key": image_key,
                    "alt": {"tag": "plain_text", "content": title},
                    "mode": "crop_center",
                    "preview": True,
                }
            )
        elements.extend(
            [
                {"tag": "div", "text": {"tag": "lark_md", "content": title_md}},
                {"tag": "div", "fields": fields},
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "▶ 观看视频"},
                            "type": "primary",
                            "url": content_url,
                        }
                    ],
                },
            ]
        )

        card = {
            "config": {"wide_screen_mode": False},
            "header": {
                "title": {"tag": "plain_text", "content": header_title},
                "template": "blue" if is_new_creator else "green",
            },
            "elements": elements,
        }

        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook_url, json={"msg_type": "interactive", "card": card})
