"""个股分析 API 测试。download_fundamentals 被 mock，不触网。"""

from unittest.mock import AsyncMock, patch

from app.services.fundamentals.base import DownloadedArtifact, DownloadOutcome


class TestFundamentalsApi:
    async def test_list_sources(self, client, auth_headers):
        resp = await client.get("/api/fundamentals/sources", headers=auth_headers)
        assert resp.status_code == 200
        names = {s["name"] for s in resp.json()}
        assert {"sec_edgar", "fmp"} <= names

    async def test_sources_requires_auth(self, client):
        resp = await client.get("/api/fundamentals/sources")
        assert resp.status_code == 401

    async def test_download_returns_manifest(self, client, auth_headers):
        fake = [
            DownloadOutcome(
                source="sec_edgar",
                artifacts=[
                    DownloadedArtifact(
                        source="sec_edgar",
                        doc_type="10-K",
                        file_path="/tmp/AAPL/sec_edgar/10-K/x.htm",
                        title="10-K 2024-09-28",
                        url="https://sec.gov/x",
                        period="2024-09-28",
                        bytes_written=42,
                    )
                ],
            ),
            DownloadOutcome(source="fmp", skipped=True, message="FMP_API_KEY 未配置"),
        ]
        with patch(
            "app.api.fundamentals.download_fundamentals",
            new=AsyncMock(return_value=fake),
        ) as mock_dl:
            resp = await client.post(
                "/api/fundamentals/download",
                headers=auth_headers,
                json={"ticker": "aapl"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ticker"] == "AAPL"
        assert len(body["results"]) == 2
        sec = body["results"][0]
        assert sec["source"] == "sec_edgar"
        assert sec["artifacts"][0]["doc_type"] == "10-K"
        assert body["results"][1]["skipped"] is True
        # ticker 归一化后传入 service
        mock_dl.assert_awaited_once()
        assert (
            mock_dl.await_args.kwargs.get("ticker") == "AAPL"
            or mock_dl.await_args.args[0] == "AAPL"
        )

    async def test_download_passes_sources_filter(self, client, auth_headers):
        with patch(
            "app.api.fundamentals.download_fundamentals",
            new=AsyncMock(return_value=[]),
        ) as mock_dl:
            resp = await client.post(
                "/api/fundamentals/download",
                headers=auth_headers,
                json={"ticker": "MSFT", "sources": ["fmp"]},
            )
        assert resp.status_code == 200
        assert mock_dl.await_args.kwargs.get("sources") == ["fmp"]

    async def test_blank_ticker_rejected(self, client, auth_headers):
        resp = await client.post(
            "/api/fundamentals/download",
            headers=auth_headers,
            json={"ticker": "  "},
        )
        assert resp.status_code == 400

    async def test_download_requires_auth(self, client):
        resp = await client.post("/api/fundamentals/download", json={"ticker": "AAPL"})
        assert resp.status_code == 401


class TestFundamentalsFileDownload:
    async def test_serves_file_inside_base_dir(self, client, auth_headers, tmp_path):
        target = tmp_path / "AAPL" / "fmp" / "ratios.json"
        target.parent.mkdir(parents=True)
        target.write_text('{"ok": true}')
        with patch(
            "app.api.fundamentals.fundamentals_base_dir", return_value=tmp_path
        ):
            resp = await client.get(
                "/api/fundamentals/files",
                headers=auth_headers,
                params={"path": str(target)},
            )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert "ratios.json" in resp.headers.get("content-disposition", "")

    async def test_path_traversal_blocked(self, client, auth_headers, tmp_path):
        outside = tmp_path.parent / "secret.txt"
        outside.write_text("secret")
        with patch(
            "app.api.fundamentals.fundamentals_base_dir", return_value=tmp_path
        ):
            resp = await client.get(
                "/api/fundamentals/files",
                headers=auth_headers,
                params={"path": str(outside)},
            )
        assert resp.status_code == 403

    async def test_missing_file_returns_404(self, client, auth_headers, tmp_path):
        with patch(
            "app.api.fundamentals.fundamentals_base_dir", return_value=tmp_path
        ):
            resp = await client.get(
                "/api/fundamentals/files",
                headers=auth_headers,
                params={"path": str(tmp_path / "AAPL" / "nope.json")},
            )
        assert resp.status_code == 404

    async def test_file_download_requires_auth(self, client):
        resp = await client.get("/api/fundamentals/files", params={"path": "/x"})
        assert resp.status_code == 401
