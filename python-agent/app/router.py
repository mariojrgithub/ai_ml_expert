from typing import Any, Dict


def classify_intent(message: str) -> Dict[str, Any]:
    text = message.lower()
    intent = "QA"
    domain = "general"

    if "mongodb" in text or "mongo query" in text or "aggregate(" in text or "find(" in text:
        intent, domain = "MONGO", "mongodb"
    elif "sql" in text or "select " in text or "query table" in text:
        intent, domain = "SQL", "sql"
    elif any(token in text for token in [
        "write code", "python", "java", "spring boot", "function", "class", "method", "api endpoint"
    ]):
        intent = "CODE"
        if "java" in text or "spring boot" in text:
            domain = "java"
        elif "python" in text:
            domain = "python"
        else:
            domain = "code"

    return {
        "intent": intent,
        "domain": domain,
        "confidence": 0.85,
    }


def plan_context(message: str, intent: str) -> Dict[str, bool]:
    text = message.lower()
    freshness_markers = ["latest", "current", "today", "recent", "newest"]

    return {
        "needs_rag": intent in {"QA", "SQL", "MONGO", "CODE"},
        "needs_web_search": any(marker in text for marker in freshness_markers),
    }