"""依赖接线冒烟检查：声明的运行期依赖必须在环境中真实可用。

这类测试故意**不打桩**——它的价值正是发现「requirements 声明了、但运行环境没装」
这类环境缺口（如 docker 镜像漏装 yt-dlp、系统缺 ffmpeg）。功能测试为了不真打外网
会把下载/转写后端 mock 掉，于是永远走不到真正的 ``import yt_dlp`` / 调 ffmpeg，
环境缺依赖就被掩盖了——本次 “No module named 'yt_dlp'” 正是这样溜过测试的。
"""

import shutil

from app.services.content_analysis import backends


def test_yt_dlp_importable():
    """下载链路依赖的 pip 包 yt-dlp 必须可导入。"""
    import yt_dlp  # noqa: F401


def test_ffmpeg_on_path():
    """转码/转 mp3/合并音视频/Whisper 读音频依赖系统 ffmpeg。"""
    assert shutil.which("ffmpeg") is not None, "ffmpeg 不在 PATH：内容分析的转码/转写会失败"


def test_backends_dependency_helpers_report_available():
    """status 接口暴露的依赖探测 helper 在完整环境下应为 True。"""
    assert backends.yt_dlp_available() is True
    assert backends.ffmpeg_available() is True


async def test_status_exposes_dependency_availability(client, auth_headers):
    """GET /status 应返回 yt_dlp_available / ffmpeg_available，供前端按依赖态禁用入口。"""
    resp = await client.get("/api/content-analysis/status", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "yt_dlp_available" in body
    assert "ffmpeg_available" in body
    assert isinstance(body["yt_dlp_available"], bool)
    assert isinstance(body["ffmpeg_available"], bool)


def test_ffmpeg_available_reflects_path(monkeypatch):
    """缺 ffmpeg 时 helper 必须报 False（防止误判可用）。"""
    monkeypatch.setattr(backends.shutil, "which", lambda _: None)
    assert backends.ffmpeg_available() is False
