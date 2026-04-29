import asyncio
import re
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
            async with JsonRpcStdioMcpClient(self.command, self.args) as client:
                await client.list_tools()
                result = await client.call_tool(
                    self.tool_name,
                    {"query": query, "limit": limit},
                )
                return self._normalize_result(result)
        except Exception as exc:
            raise RuntimeError(f"MCP stdio failed: {exc}") from exc

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
                        parsed = self._parse_duckduckgo_text_results(entry.get("text"))
                        if parsed is not None:
                            normalized.extend(parsed)
                        else:
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

    def _parse_duckduckgo_text_results(self, text: Any) -> List[Dict] | None:
        if not isinstance(text, str):
            return None

        stripped = text.strip()
        if not stripped:
            return None

        if stripped.startswith("No results were found"):
            return []

        if not stripped.startswith("Found ") or " search results:" not in stripped:
            return None

        pattern = re.compile(
            r"\n\n\d+\.\s+(?P<title>.*?)\n\s*URL:\s*(?P<url>.*?)\n\s*Summary:\s*(?P<summary>.*?)(?=\n\n\d+\.\s+|$)",
            flags=re.DOTALL,
        )

        matches = list(pattern.finditer("\n\n" + stripped))
        if not matches:
            return None

        results: List[Dict] = []
        for match in matches:
            results.append(
                {
                    "source": "mcp-web-search",
                    "title": match.group("title").strip(),
                    "snippet": match.group("summary").strip(),
                    "url": match.group("url").strip() or None,
                }
            )

        return results


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