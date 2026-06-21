"""下载与转写的真实后端实现（yt-dlp / Whisper）。

本模块是与外部库耦合的"接缝"：下载/转写均通过这里的函数完成，测试可对这些
函数打桩，避免真打外网或加载模型。移植自 yt-dlp-x 的 downloader.py / transcriber.py。
"""

import os
import shutil
from collections.abc import Callable
from pathlib import Path

from app.core.config import get_settings


def yt_dlp_available() -> bool:
    """下载依赖 yt-dlp 是否已安装（声明在 requirements，但镜像/环境可能漏装）。"""
    try:
        import yt_dlp  # noqa: F401

        return True
    except Exception:
        return False


def ffmpeg_available() -> bool:
    """转码/转 mp3/合并音视频/Whisper 读音频依赖系统 ffmpeg。"""
    return shutil.which("ffmpeg") is not None

PO_TOKEN_ERROR = "No video formats found"
_AUTH_ERROR_SIGNS = (
    "members-only",
    "Join this channel",
    "Sign in",
    "login required",
    "private video",
    "age-restricted",
)


def annotate_error(msg: str) -> str:
    if any(sign.lower() in (msg or "").lower() for sign in _AUTH_ERROR_SIGNS):
        return (
            msg
            + "\n\n提示：很可能是登录/会员 cookies 已过期，请在登录区重新导入新鲜 cookies 后重试。"
        )
    return msg


def _build_ydl_opts(
    kind: str, dest_dir: Path, progress_hook: Callable, cookie_path: Path | None
) -> dict:
    opts: dict = {
        "outtmpl": os.path.join(str(dest_dir), "%(title)s.%(ext)s"),
        "progress_hooks": [progress_hook],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "ignoreerrors": False,
    }
    if cookie_path and cookie_path.exists():
        opts["cookiefile"] = str(cookie_path)
    if kind == "audio":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
    else:
        opts["format"] = "bestvideo+bestaudio/best"
        opts["merge_output_format"] = "mp4"
    return opts


def download_media(
    url: str,
    kind: str,
    dest_dir: Path,
    cookie_path: Path | None,
    progress_cb: Callable[[float], None],
) -> tuple[str, str | None, str | None]:
    """下载音/视频，返回 (filepath, title, author)。阻塞调用，应在线程中运行。"""
    import yt_dlp

    def hook(d: dict) -> None:
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            progress_cb(round(downloaded / total * 100, 1) if total else 0.0)
        elif d.get("status") == "finished":
            progress_cb(100.0)

    def attempt(use_cookies: bool) -> tuple[str, dict]:
        opts = _build_ydl_opts(kind, dest_dir, hook, cookie_path if use_cookies else None)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            if kind == "audio":
                filepath = os.path.splitext(filepath)[0] + ".mp3"
            return filepath, info

    have_cookies = bool(cookie_path and cookie_path.exists())
    try:
        filepath, info = attempt(have_cookies)
    except yt_dlp.utils.DownloadError as exc:
        if have_cookies and PO_TOKEN_ERROR in str(exc):
            filepath, info = attempt(False)
        else:
            raise
    return filepath, info.get("title"), info.get("uploader") or info.get("channel")


# -- transcribe -------------------------------------------------------------


def _mlx_available() -> bool:
    try:
        import mlx_whisper  # noqa: F401

        return True
    except Exception:
        return False


def _openai_available() -> bool:
    try:
        import whisper  # noqa: F401

        return True
    except Exception:
        return False


def resolve_backend() -> str | None:
    backend = get_settings().whisper_backend
    if backend == "mlx":
        return "mlx" if _mlx_available() else None
    if backend == "openai":
        return "openai" if _openai_available() else None
    if _mlx_available():
        return "mlx"
    if _openai_available():
        return "openai"
    return None


def whisper_available() -> bool:
    return resolve_backend() is not None


def active_model_label() -> str:
    settings = get_settings()
    backend = resolve_backend()
    if backend == "mlx":
        return "mlx:" + settings.whisper_mlx_model.split("/")[-1]
    if backend == "openai":
        return "openai:" + settings.whisper_model
    return "unavailable"


def transcribe_audio(audio_path: str) -> str:
    """把音/视频文件转写为文本。阻塞调用，应在线程中运行。"""
    settings = get_settings()
    backend = resolve_backend()
    language = settings.whisper_language or None
    if backend == "mlx":
        import mlx_whisper

        kw: dict = {"path_or_hf_repo": settings.whisper_mlx_model}
        if language:
            kw["language"] = language
        result = mlx_whisper.transcribe(audio_path, **kw)
        return (result.get("text") or "").strip()
    if backend == "openai":
        import whisper

        model = whisper.load_model(settings.whisper_model)
        kw = {"language": language} if language else {}
        result = model.transcribe(audio_path, **kw)
        return (result.get("text") or "").strip()
    raise NotImplementedError("音频转文本未启用：未安装 mlx-whisper 或 openai-whisper。")
