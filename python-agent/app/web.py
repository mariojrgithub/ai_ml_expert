from typing import Dict, List

from .mcp.client import build_mcp_provider

_MAX_SNIPPET_CHARS = 500


def run_web_search(query: str) -> List[Dict]:
    provider = build_mcp_provider()
    return [] if provider is None else provider.search(query=query, limit=3)


def _truncate_snippet(snippet: str) -> str:
    """Cap snippet length to prevent the LLM being anchored on noisy web text."""
    if len(snippet) <= _MAX_SNIPPET_CHARS:
        return snippet
    return snippet[:_MAX_SNIPPET_CHARS].rsplit(" ", 1)[0] + " \u2026"


def external_context_to_text(results: List[Dict]) -> str:
    if not results:
        return "No external context."

    return "\n\n".join(
        f"Title: {r.get('title')}\nSource: {r.get('source')}\n"
        f"Snippet: {_truncate_snippet(r.get('snippet') or '')}"
        for r in results
    )