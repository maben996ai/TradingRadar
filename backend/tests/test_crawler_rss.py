import pytest
import respx
from httpx import Response

from app.services.crawlers.rss import RSSCrawler

crawler = RSSCrawler()

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Industry Feed</title>
    <link>https://example.com</link>
    <item>
      <title>芯片制程取得突破</title>
      <link>https://example.com/a</link>
      <guid>guid-a</guid>
      <description>&lt;p&gt;某半导体公司宣布新一代&lt;b&gt;制程&lt;/b&gt;量产。&lt;/p&gt;</description>
      <pubDate>Tue, 09 Jun 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Second post</title>
      <link>https://example.com/b</link>
      <description>Plain summary text</description>
      <pubDate>Mon, 08 Jun 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


PAGE_A = "<html><head><style>x{}</style></head><body><p>全文：半导体公司新一代制程量产，良率爬坡顺利。</p><script>var x=1;</script></body></html>"


def _mock_feed():
    respx.get("https://example.com/feed").mock(
        return_value=Response(200, content=RSS_XML.encode())
    )
    # 摘要过短时会抓原文页全文
    respx.get("https://example.com/a").mock(
        return_value=Response(200, text=PAGE_A, headers={"content-type": "text/html"})
    )
    respx.get("https://example.com/b").mock(return_value=Response(404))


class TestRSSFetch:
    @respx.mock
    async def test_fetch_latest_items_parses_entries(self):
        _mock_feed()
        items = await crawler.fetch_latest_items("https://example.com/feed")

        assert len(items) == 2
        first = items[0]
        assert first.title == "芯片制程取得突破"
        assert first.content_url == "https://example.com/a"
        assert first.platform_id == "guid-a"
        # 摘要过短 → 抓原文页全文；HTML/script/style 被剥离
        assert "<" not in first.raw_data["text"]
        assert "良率爬坡" in first.raw_data["text"]
        assert "var x" not in first.raw_data["text"]
        # 原文页抓取失败 → 回退到 feed 摘要
        assert items[1].raw_data["text"] == "Plain summary text"
        # 时间带时区
        assert first.published_at.tzinfo is not None

    @respx.mock
    async def test_fetch_respects_limit(self):
        _mock_feed()
        items = await crawler.fetch_latest_items("https://example.com/feed", limit=1)
        assert len(items) == 1


class TestRSSResolve:
    @respx.mock
    async def test_resolve_source_returns_feed_title(self):
        _mock_feed()
        info = await crawler.resolve_source("https://example.com/feed")
        assert info.platform_id == "https://example.com/feed"
        assert info.name == "Test Industry Feed"

    async def test_resolve_source_rejects_non_http_url(self):
        with pytest.raises(ValueError, match="Unsupported RSS feed URL"):
            await crawler.resolve_source("ftp://example.com/feed")
