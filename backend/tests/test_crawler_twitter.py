from unittest.mock import patch

import pytest
import respx
from httpx import Response

from app.services.crawlers.twitter import TwitterCrawler

crawler = TwitterCrawler()

TWITTER_USER_OK = {
    "data": {
        "type": "user",
        "userName": "testuser",
        "url": "https://x.com/testuser",
        "id": "12345",
        "name": "Test User",
        "profilePicture": "https://example.com/avatar.jpg",
    },
    "status": "success",
    "msg": "ok",
}

TWITTER_TWEETS_OK = {
    "data": {
        "pin_tweet": None,
        "tweets": [
            {
                "type": "tweet",
                "id": "tweet001",
                "url": "https://x.com/testuser/status/tweet001",
                "text": "First post about markets",
                "createdAt": "2026-06-06T12:30:00Z",
                "author": {"userName": "testuser"},
                "extendedEntities": {
                    "media": [
                        {
                            "type": "photo",
                            "media_url_https": "https://example.com/media.jpg",
                        }
                    ]
                },
            },
            {
                "type": "tweet",
                "id": "tweet002",
                "text": "Second post",
                "createdAt": "Sat Jun 06 10:00:00 +0000 2026",
                "author": {"userName": "testuser"},
            },
        ],
    },
    "has_next_page": False,
    "next_cursor": "",
    "status": "success",
    "msg": "ok",
}


class TestTwitterResolveSource:
    @respx.mock
    async def test_resolve_profile_url_returns_source_info(self):
        respx.get("https://api.twitterapi.io/twitter/user/info").mock(
            return_value=Response(200, json=TWITTER_USER_OK)
        )

        with patch("app.services.crawlers.twitter.settings") as mock_settings:
            mock_settings.twitterapi_io_api_key = "fake-key"
            source = await crawler.resolve_source("https://x.com/testuser")

        assert source.platform_id == "12345"
        assert source.name == "Test User"
        assert source.avatar_url == "https://example.com/avatar.jpg"
        assert source.profile_url == "https://x.com/testuser"

    async def test_no_api_key_raises_value_error(self):
        with patch("app.services.crawlers.twitter.settings") as mock_settings:
            mock_settings.twitterapi_io_api_key = ""
            with pytest.raises(ValueError, match="TWITTERAPI_IO_API_KEY is required"):
                await crawler.resolve_source("https://x.com/testuser")

    async def test_status_url_is_rejected(self):
        with patch("app.services.crawlers.twitter.settings") as mock_settings:
            mock_settings.twitterapi_io_api_key = "fake-key"
            with pytest.raises(ValueError, match="Unsupported X/Twitter profile URL"):
                await crawler.resolve_source("https://x.com/testuser/status/tweet001")


class TestTwitterFetchLatestVideos:
    @respx.mock
    async def test_returns_list_of_crawled_posts(self):
        respx.get("https://api.twitterapi.io/twitter/user/last_tweets").mock(
            return_value=Response(200, json=TWITTER_TWEETS_OK)
        )

        with patch("app.services.crawlers.twitter.settings") as mock_settings:
            mock_settings.twitterapi_io_api_key = "fake-key"
            posts = await crawler.fetch_latest_items("12345")

        assert len(posts) == 2
        assert posts[0].platform_id == "tweet001"
        assert posts[0].title == "First post about markets"
        assert posts[0].content_url == "https://x.com/testuser/status/tweet001"
        assert posts[0].thumbnail_url == "https://example.com/media.jpg"
        assert posts[0].published_at.year == 2026
        assert posts[1].content_url == "https://x.com/testuser/status/tweet002"

    async def test_no_api_key_returns_empty_list(self):
        with patch("app.services.crawlers.twitter.settings") as mock_settings:
            mock_settings.twitterapi_io_api_key = ""
            posts = await crawler.fetch_latest_items("12345")

        assert posts == []
