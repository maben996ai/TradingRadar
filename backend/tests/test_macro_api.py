"""市场宏观 API 测试。"""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app.models.models import MacroObservation


async def _seed(db):
    today = date.today()
    db.add_all(
        [
            MacroObservation(
                indicator_key="fed_funds_rate", date=today - timedelta(days=30), value=5.0
            ),
            MacroObservation(indicator_key="fed_funds_rate", date=today, value=5.25),
        ]
    )
    await db.commit()


class TestMacroIndicatorsEndpoint:
    async def test_requires_auth(self, client):
        resp = await client.get("/api/macro/indicators")
        assert resp.status_code == 401

    async def test_returns_dashboard(self, client, db, auth_headers):
        await _seed(db)
        resp = await client.get("/api/macro/indicators", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        item = next(i for i in data["indicators"] if i["key"] == "fed_funds_rate")
        assert item["latest"] == 5.25
        assert item["previous"] == 5.0
        assert item["judgment"] == "bearish"
        assert item["category"] == "rates"
        assert item["source"] == "FRED"
        assert item["reason"]
        assert len(item["series"]) == 2
        assert item["series"][0]["date"] <= item["series"][-1]["date"]

    async def test_empty_when_no_data(self, client, auth_headers):
        resp = await client.get("/api/macro/indicators", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["indicators"] == []


class TestMacroRefreshEndpoint:
    async def test_refresh_without_api_key_returns_502(self, client, auth_headers):
        # 未配置 FRED_API_KEY 时应返回明确错误（与运行环境的真实 key 无关）
        with patch(
            "app.services.macro.service.get_settings",
            return_value=SimpleNamespace(fred_api_key=""),
        ):
            resp = await client.post("/api/macro/refresh", headers=auth_headers)
        assert resp.status_code == 502
