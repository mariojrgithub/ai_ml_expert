"""Tests for Chunk 3 — user and assistant turns are saved during /agent/chat.

These tests require FastAPI's TestClient; they are skipped automatically
in environments where fastapi is not installed (e.g. outside Docker).
Run the full suite inside the Docker test container to exercise them.
"""
import os
import sys
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Skip the entire module when fastapi is not available.
# ---------------------------------------------------------------------------
fastapi_mod = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient

# Stub sentence_transformers before importing app (may not be installed locally).
sys.modules.setdefault("sentence_transformers", MagicMock())

# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------

def _make_client(admin_key: str = "test-admin-key") -> TestClient:
    os.environ["ADMIN_API_KEY"] = admin_key
    with (
        patch("app.main.ensure_indexes"),
        patch("app.main.general_llm"),
        patch("app.main.code_llm"),
        patch("app.main.embedding_model"),
    ):
        from app.main import app
        return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Helpers — minimal agent result
# ---------------------------------------------------------------------------

def _fake_agent_result(intent="QA", grounded=True, abstain=False):
    return {
        "final_answer": "This is the assistant answer.",
        "intent": intent,
        "domain": None,
        "warnings": [],
        "citations": [],
        "grounded": grounded,
        "trace": [],
        "run_metadata": {
            "intent": intent,
            "domain": None,
            "prompt_name": "qa",
            "prompt_version": "1",
            "model_name": "general",
            "retrieved_doc_count": 2,
            "external_result_count": 0,
            "grounded": grounded,
            "abstain": abstain,
            "relevance_score": 0.9,
            "groundedness_score": 0.8,
            "revision_count": 0,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestChatTurnPersistence:
    """Verify that /agent/chat saves both user and assistant turns."""

    def test_saves_user_and_assistant_turns(self):
        """A successful /agent/chat request saves exactly two messages."""
        saved = []

        def fake_save(session_id, role, content, **kwargs):
            saved.append({"session_id": session_id, "role": role, "content": content, **kwargs})
            return "mid"

        client = _make_client()
        with (
            patch("app.main.save_chat_message", side_effect=fake_save),
            patch("app.main.run_agent_with_trace", return_value=_fake_agent_result()),
            patch("app.main.save_execution", return_value="exec-1"),
        ):
            resp = client.post(
                "/agent/chat",
                json={"sessionId": "sess-chunk3", "message": "What is CI/CD?"},
                headers={"X-Admin-Api-Key": "test-admin-key"},
            )

        assert resp.status_code == 200, resp.text
        roles = [m["role"] for m in saved]
        assert roles == ["user", "assistant"], f"Expected [user, assistant], got {roles}"

    def test_user_turn_saved_before_agent_runs(self):
        """User turn must appear in the call order before the agent result."""
        call_order = []

        def fake_save(session_id, role, content, **kwargs):
            call_order.append(("save", role))
            return "mid"

        def fake_run(**kwargs):
            call_order.append(("run",))
            return _fake_agent_result()

        client = _make_client()
        with (
            patch("app.main.save_chat_message", side_effect=fake_save),
            patch("app.main.run_agent_with_trace", side_effect=fake_run),
            patch("app.main.save_execution", return_value="exec-1"),
        ):
            client.post(
                "/agent/chat",
                json={"sessionId": "sess-order", "message": "hello"},
                headers={"X-Admin-Api-Key": "test-admin-key"},
            )

        assert call_order[0] == ("save", "user")
        assert call_order[1] == ("run",)
        assert call_order[2] == ("save", "assistant")

    def test_assistant_turn_has_rich_metadata(self):
        """Assistant turn metadata must include intent, model, grounded, run_id."""
        saved = []

        def fake_save(session_id, role, content, **kwargs):
            saved.append({"role": role, **kwargs})
            return "mid-999"

        client = _make_client()
        with (
            patch("app.main.save_chat_message", side_effect=fake_save),
            patch("app.main.run_agent_with_trace", return_value=_fake_agent_result(intent="QA")),
            patch("app.main.save_execution", return_value="exec-meta"),
        ):
            client.post(
                "/agent/chat",
                json={"sessionId": "sess-meta", "message": "what is CI/CD?"},
                headers={"X-Admin-Api-Key": "test-admin-key"},
            )

        asst = next(m for m in saved if m["role"] == "assistant")
        meta = asst.get("metadata", {})
        assert meta.get("intent") == "QA"
        assert meta.get("model_name") == "general"
        assert meta.get("grounded") is True
        assert asst.get("run_id") == "exec-meta"

    def test_user_turn_saved_even_when_agent_raises(self):
        """User turn must be saved before the agent; if agent fails, no assistant turn."""
        saved_roles = []

        def fake_save(session_id, role, content, **kwargs):
            saved_roles.append(role)
            return "mid"

        client = _make_client(admin_key="test-admin-key")
        with (
            patch("app.main.save_chat_message", side_effect=fake_save),
            patch("app.main.run_agent_with_trace", side_effect=RuntimeError("agent boom")),
        ):
            resp = client.post(
                "/agent/chat",
                json={"sessionId": "sess-fail", "message": "trigger fail"},
                headers={"X-Admin-Api-Key": "test-admin-key"},
            )

        assert resp.status_code == 500
        assert "user" in saved_roles
        assert "assistant" not in saved_roles

