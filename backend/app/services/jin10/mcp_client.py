import json
from collections.abc import Mapping
from typing import Any

import httpx


class Jin10MCPError(RuntimeError):
    """Raised when the Jin10 MCP endpoint returns a protocol or tool error."""


class Jin10MCPClient:
    def __init__(
        self,
        server_url: str,
        bearer_token: str,
        protocol_version: str = "2025-11-25",
        timeout: float = 20,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.server_url = server_url
        self.bearer_token = bearer_token
        self.protocol_version = protocol_version
        self.timeout = timeout
        self.transport = transport
        self._request_id = 0
        self._session_id: str | None = None
        self._initialized = False

    async def __aenter__(self) -> "Jin10MCPClient":
        await self.initialize()
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def initialize(self) -> None:
        if self._initialized:
            return
        await self._request(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "TradingRadar", "version": "0.1.0"},
            },
        )
        await self._notification("notifications/initialized")
        await self.list_tools()
        await self.list_resources()
        self._initialized = True

    async def list_tools(self) -> dict[str, Any]:
        return await self._request("tools/list", {})

    async def list_resources(self) -> dict[str, Any]:
        return await self._request("resources/list", {})

    async def call_tool(self, name: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not self._initialized:
            await self.initialize()
        result = await self._request(
            "tools/call",
            {"name": name, "arguments": dict(arguments or {})},
        )
        if result.get("isError") is True:
            raise Jin10MCPError(self._readable_tool_error(result))
        return result

    async def read_resource(self, uri: str) -> dict[str, Any]:
        if not self._initialized:
            await self.initialize()
        return await self._request("resources/read", {"uri": uri})

    async def get_quote(self, code: str) -> dict[str, Any]:
        return await self._structured_tool_call("get_quote", {"code": code})

    async def get_kline(self, code: str, time: str | None = None, count: int | None = None) -> dict[str, Any]:
        arguments: dict[str, Any] = {"code": code}
        if time is not None:
            arguments["time"] = time
        if count is not None:
            arguments["count"] = count
        return await self._structured_tool_call("get_kline", arguments)

    async def list_flash(self, cursor: str | None = None) -> dict[str, Any]:
        return await self._structured_tool_call("list_flash", self._cursor_args(cursor))

    async def search_flash(self, keyword: str) -> dict[str, Any]:
        return await self._structured_tool_call("search_flash", {"keyword": keyword})

    async def list_news(self, cursor: str | None = None) -> dict[str, Any]:
        return await self._structured_tool_call("list_news", self._cursor_args(cursor))

    async def search_news(self, keyword: str, cursor: str | None = None) -> dict[str, Any]:
        arguments = {"keyword": keyword, **self._cursor_args(cursor)}
        return await self._structured_tool_call("search_news", arguments)

    async def get_news(self, news_id: str) -> dict[str, Any]:
        return await self._structured_tool_call("get_news", {"id": news_id})

    async def list_calendar(self) -> dict[str, Any]:
        return await self._structured_tool_call("list_calendar", {})

    async def _structured_tool_call(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        result = await self.call_tool(name, arguments)
        structured = result.get("structuredContent")
        if not isinstance(structured, dict):
            raise Jin10MCPError(f"Jin10 MCP tool {name} returned no structuredContent")
        return structured

    def _cursor_args(self, cursor: str | None) -> dict[str, str]:
        return {"cursor": cursor} if cursor else {}

    async def _notification(self, method: str, params: Mapping[str, Any] | None = None) -> None:
        await self._post_json({"jsonrpc": "2.0", "method": method, "params": dict(params or {})})

    async def _request(self, method: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": self._request_id, "method": method}
        if params is not None:
            payload["params"] = dict(params)

        response_payload = await self._post_json(payload)
        if "error" in response_payload:
            error = response_payload["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise Jin10MCPError(message or f"Jin10 MCP JSON-RPC error for {method}")

        result = response_payload.get("result")
        if not isinstance(result, dict):
            raise Jin10MCPError(f"Jin10 MCP method {method} returned invalid result")
        return result

    async def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.bearer_token:
            raise Jin10MCPError("JIN10_MCP_BEARER_TOKEN is required")

        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.bearer_token}",
            "MCP-Protocol-Version": self.protocol_version,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(self.server_url, json=payload, headers=headers)
            response.raise_for_status()

        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id

        if not response.content:
            return {}

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse_response(response.text)
        parsed = response.json()
        if not isinstance(parsed, dict):
            raise Jin10MCPError("Jin10 MCP response is not a JSON object")
        return parsed

    def _parse_sse_response(self, text: str) -> dict[str, Any]:
        data_lines: list[str] = []
        for line in text.splitlines():
            if line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
        for item in data_lines:
            if not item or item == "[DONE]":
                continue
            parsed = json.loads(item)
            if isinstance(parsed, dict) and ("result" in parsed or "error" in parsed):
                return parsed
        raise Jin10MCPError("Jin10 MCP SSE response did not contain a JSON-RPC message")

    def _readable_tool_error(self, result: dict[str, Any]) -> str:
        content = result.get("content")
        if isinstance(content, list):
            parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ]
            message = " ".join(part for part in parts if part).strip()
            if message:
                return message
        return "Jin10 MCP tool returned isError=true"
