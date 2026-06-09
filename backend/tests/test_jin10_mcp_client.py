import json

import httpx

from app.services.jin10.mcp_client import Jin10MCPClient


async def test_jin10_mcp_client_uses_standard_flow_and_structured_content():
    calls: list[dict] = []
    auth_headers: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        auth_headers.append(request.headers.get("Authorization"))
        payload = json.loads(request.content.decode())
        calls.append(payload)

        method = payload["method"]
        if method == "initialize":
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": "session-1"},
                json={
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"protocolVersion": "2025-11-25", "capabilities": {}},
                },
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "tools/list":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": payload["id"], "result": {"tools": []}},
            )
        if method == "resources/list":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": payload["id"], "result": {"resources": []}},
            )
        if method == "tools/call":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "structuredContent": {
                            "data": {
                                "items": [{"id": "flash-1", "content": "黄金走高"}],
                                "next_cursor": "cursor-2",
                                "has_more": True,
                            }
                        },
                        "content": [{"type": "text", "text": "readable only"}],
                    },
                },
            )
        raise AssertionError(f"Unexpected method {method}")

    client = Jin10MCPClient(
        server_url="https://mcp.jin10.com/mcp",
        bearer_token="test-token",
        transport=httpx.MockTransport(handler),
    )

    payload = await client.list_flash()

    assert [call["method"] for call in calls] == [
        "initialize",
        "notifications/initialized",
        "tools/list",
        "resources/list",
        "tools/call",
    ]
    assert calls[-1]["params"] == {"name": "list_flash", "arguments": {}}
    assert auth_headers == ["Bearer test-token"] * len(auth_headers)
    assert payload["data"]["items"][0]["content"] == "黄金走高"
