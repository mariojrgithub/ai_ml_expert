"""
Session memory — short-term conversational context scoped to a session_id.

Design rules (anti-hallucination):
- Memory is passed to the LLM in a SEPARATE template slot ({conversation_history}),
  never merged into the internal-context slot.
- Memory is tagged as "Prior session context (unverified):" in prompts.
- Memory does NOT count as grounding evidence for the groundedness checker.
- Turns are only written when grounded=True and abstain=False.
- Stale sessions are cleaned up automatically by the MongoDB TTL index on
  the sessions collection (ttl_expires field).
"""
from typing import Any, Dict, List, Tuple

from .config import settings
from .store import load_session_turns, save_session_turn, load_recent_messages, load_session_summary, upsert_session_summary

# Maximum number of prior turns to surface in the prompt.
# Keeping this small limits context pollution and token cost.
_MAX_TURNS_IN_PROMPT = 4

# How many recent chat_messages rows to fetch. Covers _MAX_TURNS_IN_PROMPT
# full turns (user + assistant each) plus one extra in case the current user
# message is the last entry and needs to be excluded.
# Override via settings.chat_history_recent_limit at runtime.
_RECENT_MSG_FETCH_LIMIT = 10


def read_session_memory(session_id: str) -> Tuple[List[Dict], str]:
    """Return (raw_turns, rendered_context_string) for use in the prompt.

    The rendered string is suitable for the {conversation_history} template slot.
    Returns ([], '') when no prior turns exist or the session is fresh.
    """
    turns = load_session_turns(session_id)
    if not turns:
        return [], ""

    # Most recent N turns, oldest first for natural reading order.
    recent = turns[-_MAX_TURNS_IN_PROMPT:]
    lines = ["Prior session context (unverified):"]
    for t in recent:
        lines.append(f"User: {t.get('user_input', '')}")
        lines.append(f"Assistant: {t.get('final_answer', '')[:400]}")
    return recent, "\n".join(lines)


def read_recent_chat_messages(
    session_id: str, current_user_input: str
) -> List[Dict[str, str]]:
    """Return recent chat messages from the chat_messages collection, oldest-first.

    Excludes the current user turn (which was saved before the agent runs)
    so it does not appear twice in the prompt context.

    Returns an empty list when ``settings.chat_history_enabled`` is False.
    Returns a list of ``{"role": ..., "content": ...}`` dicts.
    """
    if not settings.chat_history_enabled:
        return []
    limit = settings.chat_history_recent_limit or _RECENT_MSG_FETCH_LIMIT
    raw = load_recent_messages(session_id, limit=limit)
    if not raw:
        return []

    # The last saved message may be the current user turn — strip it if so.
    trimmed = list(raw)
    if trimmed and trimmed[-1].get("role") == "user" and trimmed[-1].get("content") == current_user_input:
        trimmed = trimmed[:-1]

    return [{"role": m.get("role", ""), "content": m.get("content", "")} for m in trimmed]


# ---------------------------------------------------------------------------
# Conversation formatting utilities (Chunk 5)
# ---------------------------------------------------------------------------

# Max characters per message when rendering to a prompt string. Long code
# blocks are truncated so we don't blow out the context window.
_MAX_CHARS_PER_MESSAGE = 500

# Hard ceiling on total characters for the conversation block in a prompt.
_MAX_CONVERSATION_CHARS = 3000


def format_recent_messages_as_text(
    recent_messages: List[Dict[str, str]],
    *,
    max_chars_per_message: int = _MAX_CHARS_PER_MESSAGE,
    max_total_chars: int = _MAX_CONVERSATION_CHARS,
) -> str:
    """Render ``recent_messages`` into a compact human-readable prompt string.

    Format per message::

        User: <content>
        Assistant: <content>

    Content is truncated to *max_chars_per_message* if necessary; a
    ``[...]`` marker is appended when truncation occurs.  The full block is
    further capped at *max_total_chars* (oldest messages are dropped first so
    the most recent context is preserved).

    Returns an empty string when *recent_messages* is empty.
    """
    if not recent_messages:
        return ""

    lines: List[str] = []
    for msg in recent_messages:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        if len(content) > max_chars_per_message:
            content = content[:max_chars_per_message] + " [...]"
        lines.append(f"{role}: {content}")

    # Enforce total character budget — drop oldest lines first.
    while lines and sum(len(l) for l in lines) > max_total_chars:
        lines.pop(0)

    return "\n".join(lines)


def build_conversation_context(
    recent_messages: List[Dict[str, str]],
    session_summary: str = "",
) -> str:
    """Return a labelled conversation block suitable for the {conversation_history} slot.

    When a *session_summary* is available it is included as a preamble before
    the verbatim recent messages.  This lets the LLM reference broader context
    that extends beyond the recent_messages window.

    Returns an empty string when there are no prior messages and no summary.
    """
    parts: List[str] = []
    if session_summary:
        parts.append(f"Session summary (may cover earlier context):\n{session_summary.strip()}")
    body = format_recent_messages_as_text(recent_messages)
    if body:
        parts.append(f"Prior conversation (recent turns):\n{body}")
    return "\n\n".join(parts)


def write_session_memory(
    session_id: str,
    user_input: str,
    final_answer: str,
    intent: str,
    grounded: bool,
    abstain: bool,
) -> None:
    """Persist a turn to the session store.

    Only writes when the response is grounded and not an abstain — this
    prevents polluting future turns with fabricated or low-confidence content.
    """
    if abstain or not grounded:
        return

    turn: Dict[str, Any] = {
        "user_input": user_input,
        "final_answer": final_answer,
        "intent": intent,
        "grounded": grounded,
    }
    save_session_turn(
        session_id=session_id,
        turn=turn,
        ttl_minutes=settings.session_memory_ttl_minutes,
    )


# ---------------------------------------------------------------------------
# Rolling session summary (Chunk 9)
# ---------------------------------------------------------------------------

_SUMMARY_TEMPLATE = (
    "You are a session summarizer. Given the current conversation summary (if any) "
    "and the latest user/assistant exchange, produce an updated compact summary "
    "(max 3 sentences) that captures the key topics and decisions so far. "
    "Output ONLY the updated summary — no preamble, no explanation.\n\n"
    "Current summary:\n{current_summary}\n\n"
    "Latest exchange:\nUser: {user_input}\nAssistant: {assistant_reply}\n\n"
    "Updated summary:"
)


def update_session_summary(
    session_id: str,
    user_input: str,
    assistant_reply: str,
) -> None:
    """Regenerate and persist the rolling session summary after a successful turn.

    Safe to call in a background/fire-and-forget fashion — any LLM or DB
    exception is caught and silently ignored so it never breaks the main flow.

    No-ops immediately when ``settings.chat_summary_enabled`` is False.
    """
    if not settings.chat_summary_enabled:
        return
    try:
        from .llm import general_llm
        from langchain_core.messages import HumanMessage

        current = load_session_summary(session_id)
        prompt = _SUMMARY_TEMPLATE.format(
            current_summary=current or "(none yet)",
            user_input=user_input[:500],
            assistant_reply=assistant_reply[:500],
        )
        new_summary = general_llm().invoke([HumanMessage(content=prompt)]).content.strip()
        if new_summary:
            upsert_session_summary(session_id, new_summary)
    except Exception:
        pass  # summary is non-critical; never propagate


def get_session_summary(session_id: str) -> str:
    """Return the current rolling summary for *session_id*, or ''."""
    return load_session_summary(session_id)
