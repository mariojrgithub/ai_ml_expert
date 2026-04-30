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
from .store import load_session_turns, save_session_turn

# Maximum number of prior turns to surface in the prompt.
# Keeping this small limits context pollution and token cost.
_MAX_TURNS_IN_PROMPT = 4


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
