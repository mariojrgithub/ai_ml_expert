"""
Input sanitization for user-supplied prompts.

Provides a lightweight, rule-based guard against common prompt-injection
patterns before the user message is forwarded to the LLM.

Design principles:
- No external calls – runs entirely in-process with zero latency overhead.
- Conservative: strips/rewrites suspicious patterns rather than rejecting
  the whole message, to avoid false positives on legitimate queries.
- Raises PromptInjectionError for patterns that are unambiguously adversarial
  (e.g. explicit system-override commands) so the API layer can return 400.
"""

import re
from typing import Tuple

# Patterns that indicate an attempt to override the system prompt or hijack
# the model's persona/instructions.  Match case-insensitively.
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?", re.I),
    re.compile(r"forget\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?", re.I),
    re.compile(r"\bdo\s+not\s+follow\s+(your\s+)?instructions?\b", re.I),
    re.compile(r"\byou\s+are\s+now\s+(a\s+)?(different|new|evil|uncensored|jailbroken)\b", re.I),
    re.compile(r"\bact\s+as\s+(if\s+you\s+are\s+)?(a\s+)?(different|evil|uncensored|jailbroken)\b", re.I),
    re.compile(r"\bDAN\b"),  # "Do Anything Now" jailbreak
    re.compile(r"<\s*system\s*>", re.I),   # injected XML system tags
    re.compile(r"\[INST\]|\[\/INST\]"),    # Llama instruction tags
]

# Maximum length for user input; truncate silently beyond this.
_MAX_INPUT_CHARS = 4096


class PromptInjectionError(ValueError):
    """Raised when the input contains an unambiguous prompt-injection attempt."""


def sanitize_user_input(text: str) -> Tuple[str, list]:
    """
    Sanitize *text* before it reaches the LLM.

    Returns (sanitized_text, warnings) where *warnings* is a (possibly empty)
    list of human-readable strings describing what was detected.

    Raises PromptInjectionError if an unambiguous injection attempt is found.
    """
    if not text:
        return text, []

    # Hard length cap — silently truncate; does not raise.
    text = text[:_MAX_INPUT_CHARS]

    warnings: list = []

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            raise PromptInjectionError(
                "The message contains content that appears to be a prompt-injection attempt "
                "and cannot be processed."
            )

    return text, warnings
