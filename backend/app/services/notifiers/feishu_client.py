import asyncio
import logging
import time

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

TENANT_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
IMAGE_UPLOAD_URL = "https://open.feishu.cn/open-apis/im/v1/images"

# 提前 5 分钟过期，避免临界点使用失效 token
_TOKEN_SAFETY_WINDOW = 300


class FeishuAppClient:
    """飞书自建应用客户端：负责 tenant_access_token 缓存与图片上传。"""

    def __init__(self, app_id: str | None = None, app_secret: str | None = None) -> None:
        settings = get_settings()
        self.app_id = settings.feishu_app_id if app_id is None else app_id
        self.app_secret = settings.feishu_app_secret if app_secret is None else app_secret
        self._token: str | None = None
        self._token_expires_at: float = 0
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_secret)

    async def get_tenant_access_token(self) -> str:
        if not self.configured:
            raise RuntimeError("Feishu app credentials are not configured")

        async with self._lock:
            now = time.time()
            if self._token and now < self._token_expires_at - _TOKEN_SAFETY_WINDOW:
                return self._token

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    TENANT_TOKEN_URL,
                    json={"app_id": self.app_id, "app_secret": self.app_secret},
                )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"Feishu token error: {data}")

            self._token = data["tenant_access_token"]
            self._token_expires_at = now + int(data.get("expire", 7200))
            return self._token

    async def upload_image_from_url(self, image_url: str) -> str:
        """下载外链图片并上传到飞书，返回 image_key。"""
        if not self.configured:
            raise RuntimeError("Feishu app credentials are not configured")

        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            img_resp = await client.get(image_url, headers=headers)
        img_resp.raise_for_status()
        image_bytes = img_resp.content
        content_type = img_resp.headers.get("content-type", "image/jpeg")

        token = await self.get_tenant_access_token()
        async with httpx.AsyncClient(timeout=15) as client:
            upload_resp = await client.post(
                IMAGE_UPLOAD_URL,
                headers={"Authorization": f"Bearer {token}"},
                data={"image_type": "message"},
                files={"image": ("cover.jpg", image_bytes, content_type)},
            )
        upload_resp.raise_for_status()
        payload = upload_resp.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"Feishu image upload error: {payload}")
        return payload["data"]["image_key"]


_default_client: FeishuAppClient | None = None


def get_feishu_app_client() -> FeishuAppClient:
    global _default_client
    if _default_client is None:
        _default_client = FeishuAppClient()
    return _default_client
