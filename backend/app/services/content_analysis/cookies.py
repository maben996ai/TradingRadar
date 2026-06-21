"""YouTube cookies 登录：粘贴 cookies.txt 或从本机浏览器导入，落盘到产物目录。

移植自 yt-dlp-x 的 cookies_util.py + auth.py。Google 不支持 yt-dlp 纯账号密码登录，
受限内容需用浏览器导出的 cookies（Netscape 格式）。
"""

import re
import tempfile
import time
import urllib.request
from pathlib import Path

from app.services.content_analysis.store import cookie_file

_PROBE_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

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


def _load_cookie_jar(path: Path):
    """加载 Netscape cookies 为 jar（抽出便于测试打桩，避免硬依赖 yt-dlp 安装）。"""
    from yt_dlp.cookies import YoutubeDLCookieJar

    jar = YoutubeDLCookieJar(str(path))
    jar.load(ignore_discard=True, ignore_expires=True)
    return jar


def _fetch_youtube_home(jar, timeout: int) -> str:
    """用给定 cookie jar 拉取 YouTube 主页 HTML（抽出便于测试打桩）。"""
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(
        "https://www.youtube.com/",
        headers={
            "User-Agent": _PROBE_UA,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def live_probe(timeout: int = 20) -> tuple[bool | None, str, dict]:
    """活体探测：用已保存 cookies 拉 YouTube 主页，读 ytcfg 的 LOGGED_IN 标志。

    返回 (state, message, info)，state 三态：
      True  -> YouTube 确认已登录
      False -> cookies 完整但未登录（已失效）或缺失/解析失败
      None  -> 无法判定（网络不可达 / 页面格式变化）
    """
    path = cookie_file()
    if not path.exists():
        return False, "未找到 cookies 文件", {"probe": "missing"}
    try:
        jar = _load_cookie_jar(path)
    except Exception as exc:  # noqa: BLE001
        return False, f"cookies 解析失败：{exc}", {"probe": "error"}

    try:
        html = _fetch_youtube_home(jar, timeout)
    except Exception as exc:  # noqa: BLE001
        return None, f"活体探测无法完成（网络问题？）：{exc}", {"probe": "unreachable"}

    m = re.search(r'"LOGGED_IN":\s*(true|false)', html)
    if not m:
        return None, "活体探测：无法判定登录状态（YouTube 页面格式可能已变化）", {"probe": "unknown"}
    if m.group(1) == "true":
        return True, "活体探测：YouTube 确认已登录", {"probe": "logged_in"}
    return (
        False,
        "活体探测：cookies 未通过 YouTube 登录校验（可能已失效，请重新导出）",
        {"probe": "logged_out"},
    )


def clear_cookies() -> None:
    """删除已保存的 cookies 文件，幂等（文件不存在不报错）。"""
    path = cookie_file()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _merge_probe(base_msg: str) -> str:
    """保存 cookies 成功后追加一次活体探测信息（探测不可达/失败不影响保存）。"""
    try:
        _state, probe_msg, _info = live_probe()
    except Exception:  # noqa: BLE001
        return base_msg
    return f"{base_msg}；{probe_msg}"


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
        # 保存成功后并入活体探测信息；探测失败或不可达不回滚已保存 cookies。
        return True, _merge_probe(msg)
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
    ok, msg = validate_cookie_file()
    if not ok:
        return False, msg
    # 保存成功后并入活体探测信息；探测失败或不可达不回滚已保存 cookies。
    return True, _merge_probe(msg)


def cookies_present() -> bool:
    return cookie_file().exists()
