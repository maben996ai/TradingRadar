from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.services.crawlers.jin10 import (
    JIN10_CALENDAR_EXTERNAL_ID,
    JIN10_FLASH_EXTERNAL_ID,
    JIN10_NEWS_EXTERNAL_ID,
    Jin10FlashCrawler,
)


async def test_jin10_flash_crawler_maps_structured_flash_items():
    crawler = Jin10FlashCrawler()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.list_flash = AsyncMock(
        return_value={
            "data": {
                "items": [
                    {
                        "id": "flash-1",
                        "content": "美联储官员发表讲话",
                        "time": "2026-06-09T01:02:03Z",
                        "url": "https://example.com/flash-1",
                    }
                ],
                "next_cursor": None,
                "has_more": False,
            }
        }
    )

    with (
        patch("app.services.crawlers.jin10.get_settings") as mock_settings,
        patch("app.services.crawlers.jin10.Jin10MCPClient", return_value=mock_client),
    ):
        mock_settings.return_value.jin10_mcp_bearer_token = "token"
        mock_settings.return_value.jin10_mcp_server_url = "https://mcp.jin10.com/mcp"
        mock_settings.return_value.jin10_mcp_protocol_version = "2025-11-25"
        items = await crawler.fetch_latest_items(JIN10_FLASH_EXTERNAL_ID, limit=10)

    assert len(items) == 1
    assert items[0].platform_id == "flash-1"
    assert items[0].title == "美联储官员发表讲话"
    assert items[0].content_url == "https://example.com/flash-1"
    assert items[0].published_at == datetime(2026, 6, 9, 1, 2, 3, tzinfo=UTC)
    assert items[0].raw_data["text"] == "美联储官员发表讲话"
    assert items[0].raw_data["jin10_category"] == "flash"


async def test_jin10_crawler_maps_structured_news_items():
    crawler = Jin10FlashCrawler()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.list_news = AsyncMock(
        return_value={
            "data": {
                "items": [
                    {
                        "id": "news-1",
                        "title": "美股收盘总结",
                        "introduction": "科技股走强",
                        "time": "2026-06-09T02:00:00+08:00",
                        "url": "https://example.com/news-1",
                    }
                ],
                "next_cursor": None,
                "has_more": False,
            }
        }
    )

    with (
        patch("app.services.crawlers.jin10.get_settings") as mock_settings,
        patch("app.services.crawlers.jin10.Jin10MCPClient", return_value=mock_client),
    ):
        mock_settings.return_value.jin10_mcp_bearer_token = "token"
        mock_settings.return_value.jin10_mcp_server_url = "https://mcp.jin10.com/mcp"
        mock_settings.return_value.jin10_mcp_protocol_version = "2025-11-25"
        items = await crawler.fetch_latest_items(JIN10_NEWS_EXTERNAL_ID, limit=10)

    assert len(items) == 1
    assert items[0].platform_id == "news-1"
    assert items[0].title == "美股收盘总结"
    assert items[0].raw_data["jin10_category"] == "news"


async def test_jin10_crawler_maps_calendar_items():
    crawler = Jin10FlashCrawler()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.list_calendar = AsyncMock(
        return_value={
            "data": [
                {
                    "pub_time": "2026-06-09T20:30:00+08:00",
                    "star": 3,
                    "title": "美国5月CPI年率",
                    "previous": "2.3%",
                    "consensus": "2.4%",
                    "actual": "",
                    "affect_txt": "利多黄金",
                }
            ]
        }
    )

    with (
        patch("app.services.crawlers.jin10.get_settings") as mock_settings,
        patch("app.services.crawlers.jin10.Jin10MCPClient", return_value=mock_client),
    ):
        mock_settings.return_value.jin10_mcp_bearer_token = "token"
        mock_settings.return_value.jin10_mcp_server_url = "https://mcp.jin10.com/mcp"
        mock_settings.return_value.jin10_mcp_protocol_version = "2025-11-25"
        items = await crawler.fetch_latest_items(JIN10_CALENDAR_EXTERNAL_ID, limit=10)

    assert len(items) == 1
    assert items[0].title == "美国5月CPI年率"
    assert items[0].published_at == datetime(2026, 6, 9, 12, 30, tzinfo=UTC)
    assert items[0].raw_data["jin10_category"] == "calendar"
    assert "前值: 2.3%" in items[0].raw_data["text"]


async def test_jin10_crawler_treats_naive_calendar_times_as_beijing_time():
    crawler = Jin10FlashCrawler()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.list_calendar = AsyncMock(
        return_value={
            "data": [
                {
                    "pub_time": "2026-06-10 20:30",
                    "star": 3,
                    "title": "美国5月未季调CPI年率",
                }
            ]
        }
    )

    with (
        patch("app.services.crawlers.jin10.get_settings") as mock_settings,
        patch("app.services.crawlers.jin10.Jin10MCPClient", return_value=mock_client),
    ):
        mock_settings.return_value.jin10_mcp_bearer_token = "token"
        mock_settings.return_value.jin10_mcp_server_url = "https://mcp.jin10.com/mcp"
        mock_settings.return_value.jin10_mcp_protocol_version = "2025-11-25"
        items = await crawler.fetch_latest_items(JIN10_CALENDAR_EXTERNAL_ID, limit=10)

    assert len(items) == 1
    assert items[0].published_at == datetime(2026, 6, 10, 12, 30, tzinfo=UTC)


async def test_jin10_calendar_keeps_one_year_history_and_three_month_future_window():
    crawler = Jin10FlashCrawler()
    now = datetime.now(UTC)
    in_window = now + timedelta(days=30)
    old = now - timedelta(days=370)
    too_far = now + timedelta(days=120)

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.list_calendar = AsyncMock(
        return_value={
            "data": [
                {"pub_time": old.isoformat(), "title": "过旧事件"},
                {"pub_time": in_window.isoformat(), "title": "未来一个月事件"},
                {"pub_time": too_far.isoformat(), "title": "未来四个月事件"},
            ]
        }
    )

    with (
        patch("app.services.crawlers.jin10.get_settings") as mock_settings,
        patch("app.services.crawlers.jin10.Jin10MCPClient", return_value=mock_client),
    ):
        mock_settings.return_value.jin10_mcp_bearer_token = "token"
        mock_settings.return_value.jin10_mcp_server_url = "https://mcp.jin10.com/mcp"
        mock_settings.return_value.jin10_mcp_protocol_version = "2025-11-25"
        items = await crawler.fetch_latest_items(JIN10_CALENDAR_EXTERNAL_ID, limit=10)

    assert [item.title for item in items] == ["未来一个月事件"]
