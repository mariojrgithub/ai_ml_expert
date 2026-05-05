"""Tests for Chunk 7 — follow-up intent detection using recent_messages."""
from app.router import classify_intent


def _am(content, intent=None, domain=None):
    """Make an assistant message dict."""
    msg = {"role": "assistant", "content": content}
    if intent:
        msg["intent"] = intent
    if domain:
        msg["domain"] = domain
    return msg


def _um(content):
    return {"role": "user", "content": content}


# ---------------------------------------------------------------------------
# No memory — behavior must be identical to calling without recent_messages
# ---------------------------------------------------------------------------

def test_no_recent_messages_unchanged():
    result = classify_intent("What is Docker?")
    result2 = classify_intent("What is Docker?", recent_messages=[])
    assert result["intent"] == result2["intent"]
    assert result["domain"] == result2["domain"]


# ---------------------------------------------------------------------------
# Explicit intent overrides follow-up detection
# ---------------------------------------------------------------------------

def test_explicit_mongo_not_overridden():
    """Explicit aggregate( signal must still classify as MONGO even with CODE history."""
    recent = [_am("Here is the Python code...", intent="CODE", domain="python")]
    result = classify_intent("show me aggregate(pipeline)", recent_messages=recent)
    assert result["intent"] == "MONGO"


def test_explicit_sql_not_overridden():
    recent = [_am("Here is the Python function...", intent="CODE", domain="python")]
    result = classify_intent("SELECT * FROM users", recent_messages=recent)
    assert result["intent"] == "SQL"


# ---------------------------------------------------------------------------
# Follow-up: inherits prior intent from assistant metadata
# ---------------------------------------------------------------------------

def test_followup_inherits_code_intent_via_metadata():
    """'convert it to Java' with CODE history should return CODE."""
    recent = [
        _um("Write a Python bubble sort"),
        _am("Here's the bubble sort in Python...", intent="CODE", domain="python"),
    ]
    result = classify_intent("now convert it to Java", recent_messages=recent)
    assert result["intent"] == "CODE"


def test_followup_inherits_sql_intent_via_metadata():
    recent = [
        _um("Write a SQL query for top sales"),
        _am("SELECT product, SUM(sales)...", intent="SQL", domain="sql"),
    ]
    result = classify_intent("now add a WHERE clause", recent_messages=recent)
    assert result["intent"] == "SQL"


def test_followup_inherits_mongo_intent_via_metadata():
    recent = [
        _um("Write a MongoDB aggregation"),
        _am("db.collection.aggregate([...])", intent="MONGO", domain="mongodb"),
    ]
    result = classify_intent("add a $match stage to that", recent_messages=recent)
    assert result["intent"] == "MONGO"


# ---------------------------------------------------------------------------
# Follow-up: referential short messages
# ---------------------------------------------------------------------------

def test_short_message_inherits_code_domain():
    recent = [_am("Here is the code snippet...", intent="CODE", domain="java")]
    result = classify_intent("make it faster", recent_messages=recent)
    assert result["intent"] == "CODE"


def test_the_result_referential_inherits_intent():
    recent = [_am("The SQL result shows...", intent="SQL", domain="sql")]
    result = classify_intent("explain the result", recent_messages=recent)
    assert result["intent"] == "SQL"


# ---------------------------------------------------------------------------
# Non-followup: longer message without referential markers
# ---------------------------------------------------------------------------

def test_long_non_referential_message_uses_own_intent():
    recent = [_am("Here is Python code...", intent="CODE", domain="python")]
    result = classify_intent(
        "what are the trade-offs between relational and document databases in large scale systems",
        recent_messages=recent,
    )
    assert result["intent"] == "QA"


# ---------------------------------------------------------------------------
# Content-based inference (no metadata)
# ---------------------------------------------------------------------------

def test_infers_code_intent_from_content_keywords():
    """Falls back to content keywords when metadata is absent."""
    recent = [{"role": "assistant", "content": "Here is some python code for sorting..."}]
    result = classify_intent("make it use recursion", recent_messages=recent)
    assert result["intent"] == "CODE"
