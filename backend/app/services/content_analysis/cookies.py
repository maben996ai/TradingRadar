"""YouTube cookies 登录：粘贴 cookies.txt 或从本机浏览器导入，落盘到产物目录。

移植自 yt-dlp-x 的 cookies_util.py + auth.py。Google 不支持 yt-dlp 纯账号密码登录，
受限内容需用浏览器导出的 cookies（Netscape 格式）。
"""

import tempfile
import time
from pathlib import Path

from app.services.content_analysis.store import cookie_file

AUTH_COOKIE_NAMES = {
    "SID",
    "__Secure-1PSID",
    "__Secure-3PSID",
    "SAPISID",
    "__Secure-1PSAPISID",
    "__Secure-3PSAPISID",
    "LOGIN_INFO",
}


def _inspect_jar(jar) -> tuple[set, float | None]:
    found: set = set()
    nearest_expiry: float | None = None
    for c in jar:
        if "youtube.com" not in c.domain and "google.com" not in c.domain:
            continue
        if c.name in AUTH_COOKIE_NAMES:
            found.add(c.name)
            if c.expires:
                nearest_expiry = (
                    c.expires if nearest_expiry is None else min(nearest_expiry, c.expires)
                )
    return found, nearest_expiry


def validate_cookie_file(path: Path | None = None) -> tuple[bool, str]:
    from yt_dlp.cookies import YoutubeDLCookieJar

    path = path or cookie_file()
    if not path.exists():
        return False, "未找到 cookies 文件"
    jar = YoutubeDLCookieJar(str(path))
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except Exception as exc:  # noqa: BLE001
        return False, f"cookies 文件解析失败：{exc}"
    found, nearest_expiry = _inspect_jar(jar)
    if not found:
        return False, "cookies 中未发现 YouTube 登录态（缺少 SID/LOGIN_INFO 等）"
    if nearest_expiry and nearest_expiry < time.time():
        return False, "登录 cookies 已过期，请重新登录浏览器后再导出"
    return True, f"检测到有效登录态（auth cookies: {', '.join(sorted(found))}）"


def save_text_cookies(text: str) -> tuple[bool, str]:
    from yt_dlp.cookies import YoutubeDLCookieJar  # noqa: F401  确保 yt-dlp 可用

    if not text or not text.strip():
        return False, "cookies 内容为空"
    dest = cookie_file()
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(text if text.startswith("# Netscape") else "# Netscape HTTP Cookie File\n" + text)
        tmp_path = Path(tmp.name)
    try:
        ok, msg = validate_cookie_file(tmp_path)
        if not ok:
            return False, msg
        tmp_path.replace(dest)
        return True, msg
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def import_from_browser(browser: str, profile: str | None = None) -> tuple[bool, str]:
    from yt_dlp.cookies import (
        SUPPORTED_BROWSERS,
        YoutubeDLCookieJar,
        extract_cookies_from_browser,
    )

    browser = (browser or "").lower()
    if browser not in SUPPORTED_BROWSERS:
        return False, f"不支持的浏览器：{browser}（可选：{', '.join(sorted(SUPPORTED_BROWSERS))}）"
    try:
        jar = extract_cookies_from_browser(browser, profile or None)
    except Exception as exc:  # noqa: BLE001
        return False, f"读取浏览器 cookies 失败：{exc}"
    out = YoutubeDLCookieJar(str(cookie_file()))
    for c in jar:
        out.set_cookie(c)
    out.save(ignore_discard=True, ignore_expires=True)
    return validate_cookie_file()


def cookies_present() -> bool:
    return cookie_file().exists()
