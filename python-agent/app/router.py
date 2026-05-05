from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Keyword sets per domain used for sub-domain detection.
# Order matters in _detect_*_domain: more specific domains are checked first.
# ---------------------------------------------------------------------------
_DL_KEYWORDS: List[str] = [
    "pytorch", "tensorflow", "keras", "neural network", "deep learning",
    "cnn", "rnn", "lstm", "transformer", "backprop", "gradient descent",
    "epoch", "batch size", "autograd", "embedding layer", "attention",
]
_DS_KEYWORDS: List[str] = [
    "pandas", "numpy", "dataframe", "data analysis", "matplotlib",
    "seaborn", "sklearn", "scikit-learn", "data science", "pivot table",
    "groupby", "merge dataframe", "csv",
]
_ALGO_KEYWORDS: List[str] = [
    "algorithm", "data structure", "sorting", "graph traversal", "binary search",
    "big o", "complexity", "linked list", "hash table", "dynamic programming",
    "breadth first", "depth first", "tree", "heap", "trie",
]
_SEC_KEYWORDS: List[str] = [
    "security", "hacking", "exploit", "vulnerability", "encryption", "cipher",
    "penetration", "ctf", "malware", "packet sniff", "reverse engineering",
    "fuzzing", "payload", "injection",
]
_FIN_KEYWORDS: List[str] = [
    "finance", "trading", "portfolio", "quant", "stock", "derivative",
    "option pricing", "risk", "black-scholes", "bond", "yield curve",
    "sharpe", "volatility", "backtest",
]
_ML_KEYWORDS: List[str] = [
    "machine learning", "bayesian", "linear algebra", "matrix", "regression",
    "classification", "clustering", "probability", "naive bayes", "random forest",
    "gradient boost", "cross validation", "feature engineering",
]
_PLATFORM_KEYWORDS: List[str] = [
    "platform engineering", "devops", "kubernetes", "docker", "infrastructure",
    "ci/cd", "aws", "cloud", "helm", "terraform", "ansible", "pipeline",
    "service mesh", "observability",
]

_CODE_REQUEST_MARKERS: List[str] = [
    "write code", "generate code", "implement", "build a function",
    "create a function", "code snippet", "refactor", "debug this code",
    "fix this code", "write a script", "show me code",
]


def _detect_code_domain(text: str) -> str:
    """Return the most specific domain for a CODE-intent question."""
    if "java" in text or "spring boot" in text or "spring" in text or "jvm" in text:
        return "java"
    if any(kw in text for kw in _DL_KEYWORDS):
        return "deep_learning"
    if any(kw in text for kw in _DS_KEYWORDS):
        return "data_science"
    if any(kw in text for kw in _SEC_KEYWORDS):
        return "security"
    if any(kw in text for kw in _FIN_KEYWORDS):
        return "finance"
    if any(kw in text for kw in _ALGO_KEYWORDS):
        return "algorithms"
    if "python" in text:
        return "python"
    return "code"


def _detect_subject_domain(text: str) -> str:
    """Return the subject domain for a QA-intent question (drives reranker bonus)."""
    if "java" in text or "spring boot" in text or "spring" in text:
        return "java"
    if any(kw in text for kw in _DL_KEYWORDS):
        return "deep_learning"
    if any(kw in text for kw in _DS_KEYWORDS):
        return "data_science"
    if any(kw in text for kw in _SEC_KEYWORDS):
        return "security"
    if any(kw in text for kw in _FIN_KEYWORDS):
        return "finance"
    if any(kw in text for kw in _ALGO_KEYWORDS):
        return "algorithms"
    if any(kw in text for kw in _ML_KEYWORDS):
        return "ml"
    if any(kw in text for kw in _PLATFORM_KEYWORDS):
        return "platform"
    if "python" in text:
        return "python"
    if "mongodb" in text or "mongo" in text:
        return "mongodb"
    if "sql" in text:
        return "sql"
    return "general"


def _looks_like_code_request(text: str) -> bool:
    if any(marker in text for marker in _CODE_REQUEST_MARKERS):
        return True
    if "```" in text:
        return True
    # Typical direct programming asks without explicit "write code" phrasing.
    return text.startswith("how do i code") or text.startswith("how to code")


# Referential phrases that signal a follow-up without new explicit intent markers.
_FOLLOWUP_MARKERS: List[str] = [
    " it ", " it.", " it?", "that ", "the result", "the output", "the code",
    "the query", "the function", "the script", "the example", "the snippet",
    "convert it", "rewrite it", "translate it", "now do", "do the same",
    "same but", "same thing", "change it", "make it", "turn it",
]


def _is_likely_followup(text: str, detected_intent: str) -> bool:
    """Return True when the message looks like a contextual follow-up.

    Criteria: the message is short (≤ 12 tokens) OR contains referential
    follow-up markers, AND the detected intent is the weak default QA.
    We only override a weak QA detection, not MONGO/SQL/CODE that was
    already explicitly detected.
    """
    if detected_intent != "QA":
        return False
    padded = f" {text} "
    has_marker = any(m in padded for m in _FOLLOWUP_MARKERS)
    is_short = len(text.split()) <= 12
    return has_marker or is_short


# Maps metadata domain strings stored in assistant messages back to intent.
_DOMAIN_TO_INTENT: Dict[str, str] = {
    "sql": "SQL",
    "mongodb": "MONGO",
    "java": "CODE",
    "python": "CODE",
    "deep_learning": "CODE",
    "data_science": "CODE",
    "algorithms": "CODE",
    "security": "CODE",
    "finance": "CODE",
    "code": "CODE",
}


def _infer_prior_intent_from_history(
    recent_messages: List[Dict[str, str]]
) -> tuple:
    """Return (intent, domain) from the most recent assistant turn, or (None, None)."""
    for msg in reversed(recent_messages):
        if msg.get("role") == "assistant":
            # Prefer explicit intent/domain stored directly on the message.
            meta_intent = msg.get("intent")
            meta_domain = msg.get("domain")
            # Also check nested metadata dict (populated from assistant saves in main.py).
            if not meta_intent and isinstance(msg.get("metadata"), dict):
                meta_intent = msg["metadata"].get("intent")
                meta_domain = msg["metadata"].get("domain") or meta_domain
            if meta_intent:
                return meta_intent, meta_domain
            # Fallback: infer from content keywords in the assistant's last reply.
            content = msg.get("content", "").lower()
            for domain, intent in _DOMAIN_TO_INTENT.items():
                if domain in content:
                    return intent, domain
    return None, None



def _intent_confidence(text: str, intent: str, domain: str) -> float:
    """Estimate classification confidence from signal strength.

    Returns a float in [0.0, 1.0]:
    - MONGO/SQL with explicit syntax signals → high (0.95)
    - CODE with explicit "write code" markers → high (0.90)
    - CODE detected only by start-of-string heuristic → medium (0.70)
    - QA with a recognisable subject domain → medium-high (0.80)
    - QA with no domain signals → lower (0.60)
    """
    if intent == "MONGO":
        # Syntax-level signals are very reliable
        if "aggregate(" in text or "find(" in text:
            return 0.95
        return 0.88
    if intent == "SQL":
        if "select " in text:
            return 0.95
        return 0.88
    if intent == "CODE":
        if any(marker in text for marker in _CODE_REQUEST_MARKERS):
            return 0.90
        return 0.70  # triggered by start-of-string heuristic only
    # QA
    if domain != "general":
        return 0.80
    return 0.60


def classify_intent(message: str, recent_messages: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    text = message.lower()
    intent = "QA"
    domain = "general"

    # Database query intents — checked first (very explicit signals)
    if "mongodb" in text or "mongo query" in text or "aggregate(" in text or "find(" in text:
        intent, domain = "MONGO", "mongodb"
    elif "sql" in text or "select " in text or "query table" in text:
        intent, domain = "SQL", "sql"
    # Code generation intent
    elif _looks_like_code_request(text):
        intent = "CODE"
        domain = _detect_code_domain(text)
    else:
        # QA — detect subject domain so the reranker can boost relevant book chunks
        domain = _detect_subject_domain(text)

    # -----------------------------------------------------------------------
    # Follow-up detection: if the query is short and referential (uses "it",
    # "that", "the result", etc.) without strong explicit signals, inherit the
    # prior intent and domain from the most recent assistant turn.
    # -----------------------------------------------------------------------
    if recent_messages:
        prior_intent, prior_domain = _infer_prior_intent_from_history(recent_messages)
        if prior_intent and _is_likely_followup(text, intent):
            intent = prior_intent
            domain = prior_domain or domain

    confidence = _intent_confidence(text, intent, domain)
    # Flag as ambiguous when the model is less certain — callers can choose to
    # prompt for clarification or apply extra hedging in the system prompt.
    ambiguity_flag = confidence < 0.75

    return {
        "intent": intent,
        "domain": domain,
        "confidence": confidence,
        "ambiguity_flag": ambiguity_flag,
    }


def plan_context(message: str, intent: str) -> Dict[str, bool]:
    from .config import settings  # local import avoids circular dependency
    text = message.lower()
    freshness_markers = ["latest", "current", "today", "recent", "newest"]
    freshness_detected = any(marker in text for marker in freshness_markers)

    return {
        "needs_rag": intent in {"QA", "SQL", "MONGO", "CODE"},
        # This flag is reserved for freshness-driven searches. The runtime also
        # falls back to web search when retrieval returns no internal context.
        "needs_web_search": settings.web_search_enabled and freshness_detected,
    }