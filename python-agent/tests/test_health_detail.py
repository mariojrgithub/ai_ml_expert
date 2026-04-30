"""Tests for app.store.get_health_detail().

MongoDB collections are mocked so no Docker / live DB is required.
"""
from unittest.mock import MagicMock, patch


def _call_health_detail(playbook_embedded, books_embedded, total_execs, grounded_execs, recent_docs):
    """Helper: patch store collections and call get_health_detail directly."""
    from app.store import get_health_detail

    playbook_col = MagicMock()
    playbook_col.count_documents.return_value = playbook_embedded

    books_col = MagicMock()
    books_col.count_documents.return_value = books_embedded

    exec_col = MagicMock()
    exec_col.count_documents.side_effect = [total_execs, grounded_execs]
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = iter(recent_docs)
    exec_col.find.return_value = cursor

    with patch("app.store.chunks_collection", return_value=playbook_col), \
         patch("app.store.book_chunks_collection", return_value=books_col), \
         patch("app.store.executions_collection", return_value=exec_col):
        return get_health_detail()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_health_detail_chunk_counts_correct():
    result = _call_health_detail(4, 10, 20, 15, [])
    assert result["chunks"]["playbook"] == 4
    assert result["chunks"]["books"] == 10
    assert result["chunks"]["total"] == 14


def test_health_detail_grounded_pct_calculation():
    result = _call_health_detail(0, 0, 100, 75, [])
    assert result["executions"]["total"] == 100
    assert result["executions"]["grounded"] == 75
    assert result["executions"]["grounded_pct"] == 75.0


def test_health_detail_grounded_pct_zero_when_no_executions():
    result = _call_health_detail(0, 0, 0, 0, [])
    assert result["executions"]["grounded_pct"] == 0.0


def test_health_detail_intent_distribution():
    recent = [
        {"intent": "QA"},
        {"intent": "QA"},
        {"intent": "CODE"},
        {"intent": "SQL"},
    ]
    result = _call_health_detail(0, 0, 4, 2, recent)
    dist = result["recent_intent_distribution"]
    assert dist["QA"] == 2
    assert dist["CODE"] == 1
    assert dist["SQL"] == 1


def test_health_detail_status_ok_on_success():
    result = _call_health_detail(2, 5, 10, 8, [])
    assert result["status"] == "ok"


def test_health_detail_status_degraded_on_db_error():
    from app.store import get_health_detail

    with patch("app.store.chunks_collection", side_effect=Exception("DB down")):
        result = get_health_detail()

    assert result["status"] == "degraded"
    assert "DB down" in result["error"]
