"""Unit tests for app.tracing.timed_node — no Docker required."""
import pytest
from app.tracing import timed_node


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_timed_node_applies_updates_to_state():
    state = {"x": 1}
    timed_node("my_node", lambda s: {"x": s["x"] + 10}, state)
    assert state["x"] == 11


def test_timed_node_appends_trace_entry():
    state = {}
    timed_node("router", lambda s: {}, state)
    assert len(state["trace"]) == 1
    assert state["trace"][0]["node"] == "router"


def test_timed_node_records_elapsed_ms():
    state = {}
    timed_node("fast_node", lambda s: {}, state)
    entry = state["trace"][0]
    assert "elapsed_ms" in entry
    assert isinstance(entry["elapsed_ms"], float)
    assert entry["elapsed_ms"] >= 0.0


def test_timed_node_accumulates_multiple_entries():
    state = {}
    timed_node("a", lambda s: {}, state)
    timed_node("b", lambda s: {}, state)
    timed_node("c", lambda s: {}, state)
    node_names = [e["node"] for e in state["trace"]]
    assert node_names == ["a", "b", "c"]


def test_timed_node_returns_state():
    state = {"val": 99}
    returned = timed_node("n", lambda s: {}, state)
    assert returned is state


# ---------------------------------------------------------------------------
# Error path
# ---------------------------------------------------------------------------

def test_timed_node_reraises_exception_from_node():
    def bad_node(s):
        raise ValueError("boom")

    state = {}
    with pytest.raises(ValueError, match="boom"):
        timed_node("bad", bad_node, state)


def test_timed_node_records_trace_entry_even_on_error():
    def bad_node(s):
        raise RuntimeError("something broke")

    state = {}
    with pytest.raises(RuntimeError):
        timed_node("failing_node", bad_node, state)

    assert len(state["trace"]) == 1
    entry = state["trace"][0]
    assert entry["node"] == "failing_node"
    assert entry["error"] == "RuntimeError"
    assert "something broke" in entry["error_detail"]


def test_timed_node_error_entry_has_elapsed_ms():
    def slow_fail(s):
        raise OSError("disk full")

    state = {}
    with pytest.raises(OSError):
        timed_node("io_node", slow_fail, state)

    assert state["trace"][0]["elapsed_ms"] >= 0.0


def test_timed_node_no_error_key_on_success():
    state = {}
    timed_node("ok", lambda s: {}, state)
    assert "error" not in state["trace"][0]
