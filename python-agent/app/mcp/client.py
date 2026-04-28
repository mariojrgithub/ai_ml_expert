import asyncio
from typing import Any, Dict, List

from ..config import settings
from .base import WebSearchProvider
from .jsonrpc_stdio_client import JsonRpcStdioMcpClient


class McpWebSearchProvider(WebSearchProvider):
    def __init__(self, command: str, args: List[str], tool_name: str = "web_search"):
        self.command = command
        self.args = args
        self.tool_name = tool_name

    def search(self, query: str, limit: int = 3) -> List[Dict]:
        return asyncio.run(self.asearch(query=query, limit=limit))

    async def asearch(self, query: str, limit: int = 3) -> List[Dict]:
        try:
            from mcp import ClientSession
            from mcp.client.stdio import StdioServerParameters, stdio_client

            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    await session.list_tools()
                    result = await session.call_tool(
                        self.tool_name,
                        {"query": query, "limit": limit},
                    )
                    return self._normalize_result(result)

        except Exception:
            async with JsonRpcStdioMcpClient(self.command, self.args) as client:
                await client.list_tools()
                result = await client.call_tool(
                    self.tool_name,
                    {"query": query, "limit": limit},
                )
                return self._normalize_result(result)

    def _normalize_result(self, result: Any) -> List[Dict]:
        if result is None:
            return []

        if isinstance(result, list):
            return [self._normalize_item(item) for item in result]

        if isinstance(result, dict):
            if "content" in result and isinstance(result["content"], list):
                normalized = []
                for entry in result["content"]:
                    if isinstance(entry, dict):
                        normalized.append(self._normalize_item(entry))
                    else:
                        normalized.append(
                            {
                                "source": "mcp",
                                "title": "content",
                                "snippet": str(entry),
                                "url": None,
                            }
                        )
                return normalized

            if "results" in result and isinstance(result["results"], list):
                return [self._normalize_item(item) for item in result["results"]]

            return [self._normalize_item(result)]

        return [
            {
                "source": "mcp",
                "title": "result",
                "snippet": str(result),
                "url": None,
            }
        ]

    def _normalize_item(self, item: Any) -> Dict:
        if isinstance(item, dict):
            return {
                "source": item.get("source", "mcp-web-search"),
                "title": item.get("title", item.get("name", "result")),
                "snippet": item.get("snippet", item.get("text", str(item))),
                "url": item.get("url"),
            }

        return {
            "source": "mcp-web-search",
            "title": "result",
            "snippet": str(item),
            "url": None,
        }


def build_mcp_provider() -> WebSearchProvider | None:
    if not settings.web_search_enabled:
        return None

    if settings.mcp_transport != "stdio":
        raise ValueError("This starter currently implements MCP stdio transport only.")

    if not settings.mcp_server_command:
        return None

    args = [part for part in settings.mcp_server_args.split(" ") if part]

    return McpWebSearchProvider(
        command=settings.mcp_server_command,
        args=args,
        tool_name=settings.mcp_web_search_tool,
    )