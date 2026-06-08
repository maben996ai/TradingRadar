"""FRED（圣路易斯联储）观测数据客户端。"""

from datetime import date

import httpx

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
REQUEST_TIMEOUT = 20.0


class FredApiError(RuntimeError):
    """FRED 调用失败或未配置 API key。"""


def parse_observations(payload: dict) -> list[tuple[date, float]]:
    """解析 FRED observations 响应，跳过缺测值（value 为 "."）。"""
    points: list[tuple[date, float]] = []
    for obs in payload.get("observations", []):
        raw_value = obs.get("value")
        raw_date = obs.get("date")
        if not raw_date or raw_value in (None, "", "."):
            continue
        try:
            points.append((date.fromisoformat(raw_date), float(raw_value)))
        except (ValueError, TypeError):
            continue
    return points


async def fetch_observations(
    series_id: str,
    units: str,
    observation_start: str,
    api_key: str,
) -> list[tuple[date, float]]:
    if not api_key:
        raise FredApiError("FRED_API_KEY 未配置")

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "units": units,
        "observation_start": observation_start,
        "sort_order": "asc",
    }
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(FRED_OBSERVATIONS_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        raise FredApiError(f"FRED 请求失败（{series_id}）：{exc}") from exc

    return parse_observations(payload)
