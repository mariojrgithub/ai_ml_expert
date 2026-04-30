"""Unit tests for app.web — snippet truncation and context formatting.

build_mcp_provider / run_web_search are not tested here (require live MCP
process). Only the pure formatting helpers are exercised.
"""
from app.web import _truncate_snippet, external_context_to_text, _MAX_SNIPPET_CHARS


# ---------------------------------------------------------------------------
# _truncate_snippet
# ---------------------------------------------------------------------------

def test_truncate_snippet_short_string_unchanged():
    s = "A short snippet."
    assert _truncate_snippet(s) == s


def test_truncate_snippet_exactly_at_limit_unchanged():
    s = "x" * _MAX_SNIPPET_CHARS
    assert _truncate_snippet(s) == s


def test_truncate_snippet_long_string_truncated():
    s = "word " * 200  # well over 500 chars
    result = _truncate_snippet(s)
    assert len(result) <= _MAX_SNIPPET_CHARS + 5  # small buffer for ellipsis


def test_truncate_snippet_ends_with_ellipsis():
    s = "word " * 200
    result = _truncate_snippet(s)
    assert result.endswith("…")


def test_truncate_snippet_splits_on_word_boundary():
    """Result must not cut in the middle of a word."""
    s = ("hello " * 100) + "CUTHERE"
    result = _truncate_snippet(s)
    assert "CUTHERE" not in result
    # Last real word before ellipsis should be complete
    without_ellipsis = result.rstrip("… ").rstrip()
    assert not without_ellipsis.endswith(" ")


def test_truncate_snippet_empty_string():
    assert _truncate_snippet("") == ""


# ---------------------------------------------------------------------------
# external_context_to_text
# ---------------------------------------------------------------------------

def test_external_context_to_text_empty_returns_no_external():
    result = external_context_to_text([])
    assert "No external context" in result


def test_external_context_to_text_single_result():
    results = [{"title": "Python 3.13", "source": "python.org", "snippet": "The new release."}]
    result = external_context_to_text(results)
    assert "Python 3.13" in result
    assert "python.org" in result
    assert "The new release." in result


def test_external_context_to_text_multiple_results_separated():
    results = [
        {"title": "A", "source": "src-a", "snippet": "first"},
        {"title": "B", "source": "src-b", "snippet": "second"},
    ]
    result = external_context_to_text(results)
    assert "first" in result
    assert "second" in result
    # Two blocks separated by a blank line
    assert "\n\n" in result


def test_external_context_to_text_truncates_long_snippet():
    long_snippet = "word " * 200
    results = [{"title": "T", "source": "S", "snippet": long_snippet}]
    result = external_context_to_text(results)
    # Snippet section must be capped
    snippet_line = [l for l in result.splitlines() if l.startswith("Snippet:")][0]
    assert len(snippet_line) <= _MAX_SNIPPET_CHARS + len("Snippet: ") + 10


def test_external_context_to_text_handles_missing_snippet():
    results = [{"title": "T", "source": "S"}]
    # Should not raise; snippet falls back to empty string
    result = external_context_to_text(results)
    assert "Snippet:" in result


def test_external_context_to_text_handles_none_snippet():
    results = [{"title": "T", "source": "S", "snippet": None}]
    result = external_context_to_text(results)
    assert "Snippet:" in result
