from typing import Dict, List

from .mcp.client import build_mcp_provider


def run_web_search(query: str) -> List[Dict]:
    provider = build_mcp_provider()
    return [] if provider is None else provider.search(query=query, limit=3)


def external_context_to_text(results: List[Dict]) -> str:
    if not results:
        return "No external context."

    return "\n\n".join(
        f"Title: {r.get('title')}\nSource: {r.get('source')}\nSnippet: {r.get('snippet')}"
        for r in results
    )