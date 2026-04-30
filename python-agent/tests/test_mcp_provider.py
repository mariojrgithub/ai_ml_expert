"""Tests for MCP client normalisation helpers and provider gating.

No live MCP process is started — all tests exercise pure Python logic.
"""
from unittest.mock import patch
from app.mcp.client import McpWebSearchProvider, build_mcp_provider


def _provider():
    return McpWebSearchProvider(command="python", args=["-V"])


# ---------------------------------------------------------------------------
# _normalize_result — dict with 'results' key
# ---------------------------------------------------------------------------

def test_normalize_result_from_dict_results():
    result = _provider()._normalize_result(
        {"results": [{"title": "A", "snippet": "B", "url": "U"}]}
    )
    assert result[0]["title"] == "A"


def test_normalize_result_from_dict_results_preserves_url():
    result = _provider()._normalize_result(
        {"results": [{"title": "T", "snippet": "S", "url": "https://example.com"}]}
    )
    assert result[0]["url"] == "https://example.com"


# ---------------------------------------------------------------------------
# _normalize_result — plain list
# ---------------------------------------------------------------------------

def test_normalize_result_from_list():
    result = _provider()._normalize_result(
        [{"title": "X", "snippet": "Y", "url": "Z"}]
    )
    assert len(result) == 1
    assert result[0]["title"] == "X"


def test_normalize_result_empty_list():
    assert _provider()._normalize_result([]) == []


# ---------------------------------------------------------------------------
# _normalize_result — None
# ---------------------------------------------------------------------------

def test_normalize_result_none_returns_empty():
    assert _provider()._normalize_result(None) == []


# ---------------------------------------------------------------------------
# _normalize_result — scalar fallback
# ---------------------------------------------------------------------------

def test_normalize_result_scalar_returns_snippet():
    result = _provider()._normalize_result("plain text")
    assert len(result) == 1
    assert result[0]["snippet"] == "plain text"


# ---------------------------------------------------------------------------
# _normalize_item fallbacks
# ---------------------------------------------------------------------------

def test_normalize_item_uses_name_when_title_missing():
    result = _provider()._normalize_item({"name": "MyTool", "snippet": "desc"})
    assert result["title"] == "MyTool"


def test_normalize_item_uses_text_when_snippet_missing():
    result = _provider()._normalize_item({"title": "T", "text": "the text"})
    assert result["snippet"] == "the text"


def test_normalize_item_scalar_returns_snippet_str():
    result = _provider()._normalize_item(42)
    assert result["snippet"] == "42"


# ---------------------------------------------------------------------------
# _parse_duckduckgo_text_results
# ---------------------------------------------------------------------------

def test_parse_duckduckgo_no_results_text():
    result = _provider()._parse_duckduckgo_text_results("No results were found for your query.")
    assert result == []


def test_parse_duckduckgo_non_string_returns_none():
    assert _provider()._parse_duckduckgo_text_results(None) is None
    assert _provider()._parse_duckduckgo_text_results(123) is None


def test_parse_duckduckgo_unrecognised_format_returns_none():
    assert _provider()._parse_duckduckgo_text_results("some random text") is None


def test_parse_duckduckgo_valid_format_returns_results():
    text = (
        "Found 1 search results:\n\n"
        "1. My Title\n"
        "   URL: https://example.com\n"
        "   Summary: This is the summary."
    )
    result = _provider()._parse_duckduckgo_text_results(text)
    assert result is not None
    assert len(result) == 1
    assert result[0]["title"] == "My Title"
    assert result[0]["url"] == "https://example.com"
    assert "summary" in result[0]["snippet"].lower()


# ---------------------------------------------------------------------------
# build_mcp_provider gating
# ---------------------------------------------------------------------------

def test_build_mcp_provider_returns_none_when_disabled():
    with patch("app.mcp.client.settings") as mock_settings:
        mock_settings.web_search_enabled = False
        assert build_mcp_provider() is None


def test_build_mcp_provider_returns_none_when_no_command():
    with patch("app.mcp.client.settings") as mock_settings:
        mock_settings.web_search_enabled = True
        mock_settings.mcp_transport = "stdio"
        mock_settings.mcp_server_command = ""
        assert build_mcp_provider() is None


def test_build_mcp_provider_raises_for_unsupported_transport():
    with patch("app.mcp.client.settings") as mock_settings:
        mock_settings.web_search_enabled = True
        mock_settings.mcp_transport = "http"
        mock_settings.mcp_server_command = "something"
        try:
            build_mcp_provider()
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "stdio" in str(e).lower()
