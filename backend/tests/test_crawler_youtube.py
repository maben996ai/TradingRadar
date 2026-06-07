from unittest.mock import patch

import pytest
import respx
from httpx import Response

from app.services.crawlers.youtube import YouTubeCrawler

crawler = YouTubeCrawler()

YOUTUBE_CHANNEL_OK = {
    "items": [
        {
            "id": "UCxxxxxx",
            "snippet": {
                "title": "Test Channel",
                "thumbnails": {"high": {"url": "https://example.com/avatar.jpg"}},
            },
        }
    ]
}

YOUTUBE_HANDLE_ID_OK = {"items": [{"id": "UCxxxxxx"}]}

YOUTUBE_PLAYLIST_ITEMS_OK = {
    "items": [
        {
            "snippet": {
                "title": "Video One",
                "publishedAt": "2024-01-15T10:00:00Z",
                "thumbnails": {"high": {"url": "https://example.com/thumb1.jpg"}},
                "resourceId": {"videoId": "vid001"},
            },
        },
        {
            "snippet": {
                "title": "Video Two",
                "publishedAt": "2024-01-10T08:00:00Z",
                "thumbnails": {},
                "resourceId": {"videoId": "vid002"},
            },
        },
    ]
}

YOUTUBE_VIDEOS_DETAILS_OK = {
    "items": [
        {
            "id": "vid001",
            "contentDetails": {"duration": "PT8M20S"},
        },
        {
            "id": "vid002",
            "contentDetails": {"duration": "PT1H8M20S"},
        },
    ]
}


class TestYouTubeResolveSource:
    @respx.mock
    async def test_resolve_channel_url_returns_source_info(self):
        respx.get("https://www.googleapis.com/youtube/v3/channels").mock(
            return_value=Response(200, json=YOUTUBE_CHANNEL_OK)
        )

        with patch("app.services.crawlers.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = "fake-key"
            source = await crawler.resolve_source("https://www.youtube.com/channel/UCxxxxxx")

        assert source.platform_id == "UCxxxxxx"
        assert source.name == "Test Channel"
        assert source.avatar_url == "https://example.com/avatar.jpg"
        assert source.profile_url == "https://www.youtube.com/channel/UCxxxxxx"

    @respx.mock
    async def test_resolve_handle_url_resolves_via_api(self):
        respx.get("https://www.googleapis.com/youtube/v3/channels").mock(
            side_effect=[
                Response(200, json=YOUTUBE_HANDLE_ID_OK),
                Response(200, json=YOUTUBE_CHANNEL_OK),
            ]
        )

        with patch("app.services.crawlers.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = "fake-key"
            source = await crawler.resolve_source("https://www.youtube.com/@testchannel")

        assert source.platform_id == "UCxxxxxx"

    async def test_no_api_key_raises_value_error(self):
        with patch("app.services.crawlers.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = ""
            with pytest.raises(ValueError, match="YOUTUBE_API_KEY is required"):
                await crawler.resolve_source("https://www.youtube.com/channel/UCxxxxxx")

    @respx.mock
    async def test_channel_not_found_raises_value_error(self):
        respx.get("https://www.googleapis.com/youtube/v3/channels").mock(
            return_value=Response(200, json={"items": []})
        )

        with patch("app.services.crawlers.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = "fake-key"
            with pytest.raises(ValueError, match="Failed to resolve YouTube creator"):
                await crawler.resolve_source("https://www.youtube.com/channel/UCxxxxxx")


class TestYouTubeFetchLatestVideos:
    @respx.mock
    async def test_returns_list_of_crawled_videos(self):
        respx.get("https://www.googleapis.com/youtube/v3/playlistItems").mock(
            return_value=Response(200, json=YOUTUBE_PLAYLIST_ITEMS_OK)
        )
        respx.get("https://www.googleapis.com/youtube/v3/videos").mock(
            return_value=Response(200, json=YOUTUBE_VIDEOS_DETAILS_OK)
        )

        with patch("app.services.crawlers.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = "fake-key"
            videos = await crawler.fetch_latest_items("UCxxxxxx")

        assert len(videos) == 2
        assert videos[0].platform_id == "vid001"
        assert videos[0].title == "Video One"
        assert videos[0].content_url == "https://www.youtube.com/watch?v=vid001"
        assert videos[0].thumbnail_url == "https://example.com/thumb1.jpg"

    @respx.mock
    async def test_published_at_is_parsed_from_iso_string(self):
        respx.get("https://www.googleapis.com/youtube/v3/playlistItems").mock(
            return_value=Response(200, json=YOUTUBE_PLAYLIST_ITEMS_OK)
        )
        respx.get("https://www.googleapis.com/youtube/v3/videos").mock(
            return_value=Response(200, json=YOUTUBE_VIDEOS_DETAILS_OK)
        )

        with patch("app.services.crawlers.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = "fake-key"
            videos = await crawler.fetch_latest_items("UCxxxxxx")

        assert videos[0].published_at.year == 2024
        assert videos[0].published_at.month == 1

    @respx.mock
    async def test_duration_is_fetched_from_videos_api_and_added_to_raw_data(self):
        respx.get("https://www.googleapis.com/youtube/v3/playlistItems").mock(
            return_value=Response(200, json=YOUTUBE_PLAYLIST_ITEMS_OK)
        )
        respx.get("https://www.googleapis.com/youtube/v3/videos").mock(
            return_value=Response(200, json=YOUTUBE_VIDEOS_DETAILS_OK)
        )

        with patch("app.services.crawlers.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = "fake-key"
            videos = await crawler.fetch_latest_items("UCxxxxxx")

        assert videos[0].raw_data["contentDetails"]["duration"] == "PT8M20S"
        assert videos[1].raw_data["contentDetails"]["duration"] == "PT1H8M20S"

    @respx.mock
    async def test_missing_videos_details_does_not_break_fetch(self):
        respx.get("https://www.googleapis.com/youtube/v3/playlistItems").mock(
            return_value=Response(200, json=YOUTUBE_PLAYLIST_ITEMS_OK)
        )
        respx.get("https://www.googleapis.com/youtube/v3/videos").mock(
            return_value=Response(200, json={"items": []})
        )

        with patch("app.services.crawlers.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = "fake-key"
            videos = await crawler.fetch_latest_items("UCxxxxxx")

        assert len(videos) == 2
        assert "contentDetails" not in videos[0].raw_data

    async def test_no_api_key_returns_empty_list(self):
        with patch("app.services.crawlers.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = ""
            videos = await crawler.fetch_latest_items("UCxxxxxx")

        assert videos == []

    @respx.mock
    async def test_items_missing_video_id_are_skipped(self):
        respx.get("https://www.googleapis.com/youtube/v3/playlistItems").mock(
            return_value=Response(
                200, json={"items": [{"snippet": {"title": "no id", "resourceId": {}}}]}
            )
        )

        with patch("app.services.crawlers.youtube.settings") as mock_settings:
            mock_settings.youtube_api_key = "fake-key"
            videos = await crawler.fetch_latest_items("UCxxxxxx")

        assert videos == []
