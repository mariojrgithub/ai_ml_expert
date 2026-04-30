"""
Response quality checkers.

Three lightweight stages run after draft generation, before final output:

    A. relevance_check   — does the answer address the question?  (rules-based)
    B. groundedness_check — are QA claims traceable to retrieved docs? (embedding)
    C. citation_check    — are sufficient citations present?  (rules-based)

Design principles:
- No external LLM calls — keeps latency low and avoids recursive hallucination.
- Checker A can trigger a revision loop (up to max_revision_attempts).
- Checkers B and C are advisory — they append warnings but do not block output.
- Memory context is never counted as grounding evidence.
"""
from typing import Dict, List, Tuple

from .config import settings


# ---------------------------------------------------------------------------
# A — Relevance check
# ---------------------------------------------------------------------------

def _token_set(text: str) -> set:
    return {t for t in text.lower().split() if len(t) > 2}


def check_relevance(user_input: str, draft_output: str) -> Tuple[float, bool]:
    """Return (relevance_score, passed).

    Score = Jaccard-style overlap between question tokens and answer tokens.
    Threshold comes from settings.checker_relevance_threshold.

    Intentionally simple — the goal is to catch completely off-topic answers,
    not to do semantic equivalence checking.
    """
    if not draft_output or not draft_output.strip():
        return 0.0, False

    q_tokens = _token_set(user_input)
    a_tokens = _token_set(draft_output)
    if not q_tokens:
        return 1.0, True

    intersection = q_tokens & a_tokens
    score = len(intersection) / max(len(q_tokens), 1)
    return round(score, 4), score >= settings.checker_relevance_threshold


# ---------------------------------------------------------------------------
# B — Groundedness check (QA-only)
# ---------------------------------------------------------------------------

def _sentence_split(text: str) -> List[str]:
    """Naive sentence splitter — avoids a heavy NLP dependency."""
    import re
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if len(p.split()) >= 4]


def check_groundedness(
    draft_output: str,
    retrieved_docs: List[Dict],
    external_results: List[Dict],
    intent: str,
) -> Tuple[float, List[str]]:
    """Return (groundedness_score, ungrounded_sentences).

    Only meaningful for QA intent. For all other intents returns (1.0, []).

    Approach: for each sentence in the draft, compute token overlap against
    the union of all retrieved/external snippets.  A sentence is considered
    grounded if its overlap score >= 0.15 (conservative threshold).
    Memory context is intentionally excluded from the evidence corpus.
    """
    if intent != 'QA':
        return 1.0, []

    # Build evidence corpus from retrieved docs + external snippets.
    evidence_texts: List[str] = []
    for d in retrieved_docs:
        t = d.get('text', '')
        if t:
            evidence_texts.append(t.lower())
    for r in external_results:
        s = r.get('snippet', '')
        if s:
            evidence_texts.append(s.lower())

    if not evidence_texts:
        # No evidence at all — every sentence is ungrounded.
        sentences = _sentence_split(draft_output)
        return 0.0, sentences

    sentences = _sentence_split(draft_output)
    if not sentences:
        return 1.0, []

    ungrounded: List[str] = []
    _GROUND_THRESHOLD = 0.12  # per-sentence token overlap threshold

    for sent in sentences:
        sent_tokens = _token_set(sent)
        if not sent_tokens:
            continue
        best_overlap = max(
            len(sent_tokens & _token_set(ev)) / max(len(sent_tokens), 1)
            for ev in evidence_texts
        )
        if best_overlap < _GROUND_THRESHOLD:
            ungrounded.append(sent)

    grounded_count = len(sentences) - len(ungrounded)
    score = round(grounded_count / len(sentences), 4) if sentences else 1.0
    return score, ungrounded


# ---------------------------------------------------------------------------
# C — Citation sufficiency check
# ---------------------------------------------------------------------------

def check_citation_sufficiency(
    intent: str,
    grounded: bool,
    citations: List[Dict],
) -> List[str]:
    """Return a list of warning strings (empty = all good).

    For grounded QA answers, at least one citation must be present.
    """
    warnings: List[str] = []
    if intent == 'QA' and grounded and not citations:
        warnings.append(
            'Grounded QA response has no citations. '
            'Consider adding source references.'
        )
    return warnings
