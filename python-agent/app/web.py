from time import monotonic
from typing import Dict, List

from .mcp.client import build_mcp_provider

_MAX_SNIPPET_CHARS = 500

# ---------------------------------------------------------------------------
# Web-search result cache — avoids redundant MCP calls for repeated queries.
# TTL-based: entries older than _WEB_CACHE_TTL_SECONDS are discarded.
# ---------------------------------------------------------------------------
_WEB_CACHE_TTL_SECONDS = 300.0  # 5 minutes
_web_cache: Dict[str, tuple] = {}  # key -> (timestamp, results)


def run_web_search(query: str) -> List[Dict]:
    now = monotonic()
    entry = _web_cache.get(query)
    if entry is not None:
        ts, results = entry
        if (now - ts) < _WEB_CACHE_TTL_SECONDS:
            return results

    provider = build_mcp_provider()
    try:
        results = [] if provider is None else provider.search(query=query, limit=3)
    except Exception:
        results = []
    _web_cache[query] = (now, results)
    return results


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