"""Tests for chat_messages storage functions in app.store.

All MongoDB interactions are mocked — these tests run without Docker.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_msg(role: str, content: str, offset_seconds: int = 0):
    return {
        "role": role,
        "content": content,
        "created_at": datetime(2024, 1, 1, 0, 0, offset_seconds, tzinfo=timezone.utc),
        "metadata": None,
    }


# ---------------------------------------------------------------------------
# save_chat_message
# ---------------------------------------------------------------------------

def test_save_chat_message_inserts_doc():
    mock_col = MagicMock()
    mock_col.insert_one.return_value.inserted_id = "abc123"

    with patch("app.store.chat_messages_collection", return_value=mock_col):
        from app.store import save_chat_message
        result_id = save_chat_message("sess-1", "user", "Hello there")

    assert result_id == "abc123"
    mock_col.insert_one.assert_called_once()
    inserted = mock_col.insert_one.call_args[0][0]
    assert inserted["session_id"] == "sess-1"
    assert inserted["role"] == "user"
    assert inserted["content"] == "Hello there"
    assert "created_at" in inserted


def test_save_chat_message_includes_optional_fields():
    mock_col = MagicMock()
    mock_col.insert_one.return_value.inserted_id = "xyz"

    with patch("app.store.chat_messages_collection", return_value=mock_col):
        from app.store import save_chat_message
        save_chat_message(
            "sess-2",
            "assistant",
            "Sure, here is the answer.",
            user_id="user-99",
            metadata={"intent": "QA", "model": "llama3"},
            run_id="run-42",
        )

    inserted = mock_col.insert_one.call_args[0][0]
    assert inserted["user_id"] == "user-99"
    assert inserted["metadata"]["intent"] == "QA"
    assert inserted["run_id"] == "run-42"


def test_save_chat_message_omits_none_optional_fields():
    mock_col = MagicMock()
    mock_col.insert_one.return_value.inserted_id = "noid"

    with patch("app.store.chat_messages_collection", return_value=mock_col):
        from app.store import save_chat_message
        save_chat_message("sess-3", "user", "No extras")

    inserted = mock_col.insert_one.call_args[0][0]
    assert "user_id" not in inserted
    assert "metadata" not in inserted
    assert "run_id" not in inserted


# ---------------------------------------------------------------------------
# load_recent_messages
# ---------------------------------------------------------------------------

def test_load_recent_messages_returns_oldest_first():
    """Mongo returns newest-first (sort -1), function must reverse."""
    newer = _make_msg("assistant", "Answer.", offset_seconds=2)
    older = _make_msg("user", "Question?", offset_seconds=0)
    # Mongo cursor returns newest first
    mock_col = MagicMock()
    mock_col.find.return_value.sort.return_value.limit.return_value = [newer, older]

    with patch("app.store.chat_messages_collection", return_value=mock_col):
        from app.store import load_recent_messages
        msgs = load_recent_messages("sess-abc", limit=8)

    assert len(msgs) == 2
    # After reversal, older should be first
    assert msgs[0]["content"] == "Question?"
    assert msgs[1]["content"] == "Answer."


def test_load_recent_messages_empty_session():
    mock_col = MagicMock()
    mock_col.find.return_value.sort.return_value.limit.return_value = []

    with patch("app.store.chat_messages_collection", return_value=mock_col):
        from app.store import load_recent_messages
        msgs = load_recent_messages("sess-unknown")

    assert msgs == []


def test_load_recent_messages_respects_limit():
    mock_col = MagicMock()
    mock_col.find.return_value.sort.return_value.limit.return_value = []

    with patch("app.store.chat_messages_collection", return_value=mock_col):
        from app.store import load_recent_messages
        load_recent_messages("sess-x", limit=4)

    # Verify .limit(4) was called
    mock_col.find.return_value.sort.return_value.limit.assert_called_once_with(4)


def test_load_recent_messages_chronological_order_multi():
    """Simulate six messages; result must be oldest-first after reversal."""
    messages = [
        _make_msg("user", f"msg{i}", offset_seconds=10 - i)
        for i in range(6)
    ]
    # Sorted newest-first as Mongo would return them
    mock_col = MagicMock()
    mock_col.find.return_value.sort.return_value.limit.return_value = messages

    with patch("app.store.chat_messages_collection", return_value=mock_col):
        from app.store import load_recent_messages
        result = load_recent_messages("sess-multi", limit=6)

    assert result == list(reversed(messages))


# ---------------------------------------------------------------------------
# clear_session_messages
# ---------------------------------------------------------------------------

def test_clear_session_messages_returns_deleted_count():
    mock_col = MagicMock()
    mock_col.delete_many.return_value.deleted_count = 5

    with patch("app.store.chat_messages_collection", return_value=mock_col):
        from app.store import clear_session_messages
        count = clear_session_messages("sess-to-clear")

    assert count == 5
    mock_col.delete_many.assert_called_once_with({"session_id": "sess-to-clear"})


def test_clear_session_messages_zero_when_empty():
    mock_col = MagicMock()
    mock_col.delete_many.return_value.deleted_count = 0

    with patch("app.store.chat_messages_collection", return_value=mock_col):
        from app.store import clear_session_messages
        count = clear_session_messages("sess-empty")

    assert count == 0


# ---------------------------------------------------------------------------
# Round-trip: save then load in chronological order
# ---------------------------------------------------------------------------

def test_save_and_load_roundtrip_order():
    """Simulate a save/load cycle with in-memory list to verify ordering."""
    stored: list = []

    def fake_insert(doc):
        stored.append(dict(doc))
        m = MagicMock()
        m.inserted_id = str(len(stored))
        return m

    def fake_find(query, projection=None):
        matched = [d for d in stored if d.get("session_id") == query.get("session_id")]
        m = MagicMock()
        # Mimic sort(-1) then limit(n)
        m.sort.return_value.limit.return_value = list(reversed(matched))
        return m

    mock_col = MagicMock()
    mock_col.insert_one.side_effect = fake_insert
    mock_col.find.side_effect = fake_find

    with patch("app.store.chat_messages_collection", return_value=mock_col):
        from app.store import save_chat_message, load_recent_messages

        save_chat_message("sess-rt", "user", "First message")
        save_chat_message("sess-rt", "assistant", "First reply")
        save_chat_message("sess-rt", "user", "Second message")

        msgs = load_recent_messages("sess-rt", limit=10)

    assert len(msgs) == 3
    assert msgs[0]["content"] == "First message"
    assert msgs[0]["role"] == "user"
    assert msgs[1]["content"] == "First reply"
    assert msgs[1]["role"] == "assistant"
    assert msgs[2]["content"] == "Second message"
