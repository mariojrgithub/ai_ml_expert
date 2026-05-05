"""Chunk 11 tests — retention feature flags from config.py."""
from unittest.mock import patch, MagicMock


def test_read_recent_chat_messages_returns_empty_when_disabled():
    """When chat_history_enabled=False, read_recent_chat_messages must return []."""
    from app.memory import read_recent_chat_messages

    with patch("app.memory.settings") as mock_settings:
        mock_settings.chat_history_enabled = False
        result = read_recent_chat_messages("sess-1", "any input")

    assert result == []


def test_read_recent_chat_messages_uses_recent_limit_from_settings():
    """chat_history_recent_limit must be forwarded as the DB limit."""
    from app.memory import read_recent_chat_messages

    with (
        patch("app.memory.settings") as mock_settings,
        patch("app.memory.load_recent_messages", return_value=[]) as mock_load,
    ):
        mock_settings.chat_history_enabled = True
        mock_settings.chat_history_recent_limit = 5
        read_recent_chat_messages("sess-2", "anything")

    mock_load.assert_called_once_with("sess-2", limit=5)


def test_update_session_summary_noop_when_summary_disabled():
    """When chat_summary_enabled=False, update_session_summary must exit without calling LLM."""
    from app.memory import update_session_summary

    with (
        patch("app.memory.settings") as mock_settings,
        patch("app.memory.load_session_summary") as mock_load,
        patch("app.memory.upsert_session_summary") as mock_upsert,
    ):
        mock_settings.chat_summary_enabled = False
        update_session_summary("sess-3", "question", "answer")

    mock_load.assert_not_called()
    mock_upsert.assert_not_called()
