"""财经日历 API 测试。"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.models.models import CalendarEvent

START = "2026-06-01T00:00:00Z"
END = "2026-07-01T00:00:00Z"


async def _seed_event(db, **kw):
    defaults = dict(
        event_key="cpi_z", kind="macro", category="inflation", title="CPI 同比",
        title_en="CPI YoY", country="US",
        scheduled_at=datetime(2026, 6, 12, 12, 30, tzinfo=UTC), all_day=False,
        importance=3, impact_assets="美元、美股", actual=3.4, previous=3.2,
        value_unit="%", source="FRED",
    )
    defaults.update(kw)
    db.add(CalendarEvent(**defaults))
    await db.commit()


class TestEventsEndpoint:
    async def test_requires_auth(self, client):
        resp = await client.get(f"/api/calendar/events?start={START}&end={END}")
        assert resp.status_code == 401

    async def test_returns_events(self, client, db, auth_headers):
        await _seed_event(db)
        resp = await client.get(
            f"/api/calendar/events?start={START}&end={END}", headers=auth_headers
        )
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) == 1
        e = events[0]
        assert e["category"] == "inflation"
        assert e["actual"] == 3.4
        assert e["importance"] == 3
        assert e["source"] == "FRED"

    async def test_category_filter(self, client, db, auth_headers):
        await _seed_event(db, event_key="cpi_z", category="inflation")
        await _seed_event(db, event_key="nfp_z", category="employment", title="非农")
        resp = await client.get(
            f"/api/calendar/events?start={START}&end={END}&categories=employment",
            headers=auth_headers,
        )
        keys = [e["event_key"] for e in resp.json()["events"]]
        assert keys == ["nfp_z"]


class TestTrackedTickers:
    async def test_crud(self, client, auth_headers):
        # 创建
        resp = await client.post(
            "/api/calendar/tracked-tickers",
            json={"ticker": "amd", "company_name": "AMD"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        created = resp.json()
        assert created["ticker"] == "AMD"  # 规范化为大写
        ticker_id = created["id"]

        # 列表
        resp = await client.get("/api/calendar/tracked-tickers", headers=auth_headers)
        assert [t["ticker"] for t in resp.json()] == ["AMD"]

        # 重复添加返回已存在，不重复
        resp = await client.post(
            "/api/calendar/tracked-tickers", json={"ticker": "AMD"}, headers=auth_headers
        )
        assert resp.status_code in (200, 201)
        resp = await client.get("/api/calendar/tracked-tickers", headers=auth_headers)
        assert len(resp.json()) == 1

        # 删除
        resp = await client.delete(
            f"/api/calendar/tracked-tickers/{ticker_id}", headers=auth_headers
        )
        assert resp.status_code == 204
        resp = await client.get("/api/calendar/tracked-tickers", headers=auth_headers)
        assert resp.json() == []


class TestRefreshEndpoint:
    async def test_refresh_seed_inserts(self, client, auth_headers):
        # 无 key → SeedProvider，离线生成精选事件
        empty = SimpleNamespace(
            fred_api_key="", trading_economics_api_key="", fmp_api_key=""
        )
        with patch("app.services.calendar.service.get_settings", return_value=empty):
            resp = await client.post("/api/calendar/refresh", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["inserted"] > 0
