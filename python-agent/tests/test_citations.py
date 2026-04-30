"""Unit tests for app.citations.format_citations — no Docker required."""
from app.citations import format_citations


def test_format_citations_empty_list_returns_empty_string():
    assert format_citations([]) == ""


def test_format_citations_single_item():
    result = format_citations([{"title": "Python Logging", "source": "internal-playbook"}])
    assert "Python Logging" in result
    assert "internal-playbook" in result


def test_format_citations_respects_max_items():
    items = [{"title": f"Doc {i}", "source": "src"} for i in range(10)]
    result = format_citations(items, max_items=3)
    assert "Doc 0" in result
    assert "Doc 1" in result
    assert "Doc 2" in result
    assert "Doc 3" not in result


def test_format_citations_default_max_is_three():
    items = [{"title": f"T{i}", "source": "s"} for i in range(5)]
    result = format_citations(items)
    assert result.count("[") == 3


def test_format_citations_starts_with_sources_label():
    result = format_citations([{"title": "X", "source": "Y"}])
    assert result.strip().startswith("Sources:")


def test_format_citations_uses_unknown_for_missing_title():
    result = format_citations([{"source": "somewhere"}])
    assert "unknown" in result


def test_format_citations_uses_unknown_for_missing_source():
    result = format_citations([{"title": "MyDoc"}])
    assert "unknown" in result


def test_format_citations_multiple_items_separated_by_semicolons():
    items = [
        {"title": "A", "source": "src-a"},
        {"title": "B", "source": "src-b"},
    ]
    result = format_citations(items)
    assert ";" in result
