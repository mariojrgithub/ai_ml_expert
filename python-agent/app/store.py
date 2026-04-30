from datetime import datetime, timezone
from typing import Any, Dict, List

from pymongo import MongoClient, TEXT
from pymongo.collection import Collection

from .config import settings

client = MongoClient(settings.mongo_uri)
db = client[settings.mongo_db]


def documents_collection() -> Collection:
    return db["documents"]


def chunks_collection() -> Collection:
    return db["chunks"]


def executions_collection() -> Collection:
    return db["executions"]


def eval_runs_collection() -> Collection:
    return db["eval_runs"]


def book_chunks_collection() -> Collection:
    return db["book_chunks"]


def sessions_collection() -> Collection:
    return db["sessions"]


def ensure_indexes() -> None:
    documents_collection().create_index([("title", TEXT), ("content", TEXT), ("domain", TEXT)])
    chunks_collection().create_index([("title", TEXT), ("text", TEXT), ("domain", TEXT)])
    book_chunks_collection().create_index([("title", TEXT), ("text", TEXT)], name="book_text_idx")
    book_chunks_collection().create_index(
        [("book_id", 1), ("chunk_index", 1)], unique=True, name="book_chunk_idx"
    )
    book_chunks_collection().create_index("source_type", name="source_type_idx")
    executions_collection().create_index("createdAt")
    executions_collection().create_index('grounded', name='exec_grounded_idx')
    eval_runs_collection().create_index('createdAt')
    # Sessions: unique by session_id + TTL expiry index for automatic cleanup.
    sessions_collection().create_index('session_id', unique=True, name='session_id_idx')
    sessions_collection().create_index('ttl_expires', expireAfterSeconds=0, name='session_ttl_idx')


def seed_sample_documents() -> int:
    docs = [
        {
            "title": "Python Logging Best Practices",
            "domain": "python",
            "source": "internal-playbook",
            "content": "Use structured logging, include correlation IDs, and avoid swallowing exceptions. Prefer explicit error handling and typed return values for service boundaries.",
        },
        {
            "title": "Spring Boot REST Design",
            "domain": "java",
            "source": "internal-playbook",
            "content": "Use request DTOs, validation annotations, clear service boundaries, and externalized configuration. Prefer WebClient for downstream HTTP integrations.",
        },
        {
            "title": "MongoDB Query Guidelines",
            "domain": "mongodb",
            "source": "internal-playbook",
            "content": "Prefer indexed filters, add limits, avoid $where, and use aggregation only when necessary. Keep queries targeted and explicit.",
        },
        {
            "title": "SQL Query Guidelines",
            "domain": "sql",
            "source": "internal-playbook",
            "content": "Default to SELECT only for assistants. Always filter by indexed columns where possible and avoid SELECT *. Add LIMIT for exploratory requests.",
        },
        {
            "title": "CI/CD Guardrails",
            "domain": "cicd",
            "source": "internal-playbook",
            "content": "Keep pipelines deterministic, pin versions, run unit tests first, then integration tests, then security scans. Separate build, test, and deploy stages.",
        },
        {
            "title": "Cloud Infrastructure Basics",
            "domain": "cloud",
            "source": "internal-playbook",
            "content": "Prefer infrastructure as code, isolate environments, enable observability by default, and use least-privilege access for workloads and pipelines.",
        },
    ]

    chunks = [
        {
            "title": d["title"],
            "domain": d["domain"],
            "source": d["source"],
            "text": d["content"],
            "embedding": None,
        }
        for d in docs
    ]

    for doc in docs:
        documents_collection().update_one(
            {"title": doc["title"]},
            {"$setOnInsert": doc},
            upsert=True,
        )

    for chunk in chunks:
        chunks_collection().update_one(
            {"title": chunk["title"]},
            {"$setOnInsert": chunk},
            upsert=True,
        )

    return len(docs)


def load_chunks_without_embeddings() -> List[Dict[str, Any]]:
    return list(chunks_collection().find({"embedding": None}))


def set_chunk_embedding(chunk_id: Any, embedding: List[float]) -> None:
    chunks_collection().update_one(
        {"_id": chunk_id},
        {"$set": {"embedding": embedding}},
    )


def all_embedded_chunks() -> List[Dict[str, Any]]:
    """Return all embedded chunks from both the internal playbook and book_chunks collections."""
    playbook = list(chunks_collection().find({"embedding": {"$type": "array"}}))
    books = list(book_chunks_collection().find({"embedding": {"$type": "array"}}))
    return playbook + books


def save_execution(payload: Dict[str, Any]) -> str:
    doc = {**payload, "createdAt": datetime.now(timezone.utc)}
    result = executions_collection().insert_one(doc)
    return str(result.inserted_id)


def save_eval_run(payload: Dict[str, Any]) -> str:
    doc = {**payload, "createdAt": datetime.now(timezone.utc)}
    result = eval_runs_collection().insert_one(doc)
    return str(result.inserted_id)


def save_session_turn(session_id: str, turn: Dict[str, Any], ttl_minutes: int = 30) -> None:
    """Append a turn to the session document, creating it if absent.
    The TTL index on ttl_expires will auto-delete idle sessions.
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=ttl_minutes)
    sessions_collection().update_one(
        {"session_id": session_id},
        {
            "$push": {"turns": {**turn, "createdAt": now}},
            "$set": {"last_active": now, "ttl_expires": expires},
            "$setOnInsert": {"session_id": session_id, "createdAt": now},
        },
        upsert=True,
    )


def load_session_turns(session_id: str) -> List[Dict[str, Any]]:
    """Return all turns for this session, or [] if the session does not exist."""
    doc = sessions_collection().find_one({"session_id": session_id}, {"turns": 1})
    if doc is None:
        return []
    return doc.get("turns", [])


def get_health_detail() -> Dict[str, Any]:
    """Gather operational health metrics from MongoDB.

    Returns a dict suitable for serialising to JSON.  Wraps all DB calls so a
    transient failure returns ``{"status": "degraded", "error": ...}`` rather
    than propagating an exception to the HTTP layer.
    """
    try:
        playbook_chunks = chunks_collection().count_documents({"embedding": {"$type": "array"}})
        book_chunks = book_chunks_collection().count_documents({"embedding": {"$type": "array"}})
        total_execs = executions_collection().count_documents({})
        grounded_execs = executions_collection().count_documents({"grounded": True})
        recent = list(
            executions_collection()
            .find({}, {"intent": 1, "grounded": 1, "_id": 0})
            .sort("createdAt", -1)
            .limit(100)
        )
        intent_counts: Dict[str, int] = {}
        for doc in recent:
            k = doc.get("intent", "UNKNOWN")
            intent_counts[k] = intent_counts.get(k, 0) + 1
        return {
            "status": "ok",
            "chunks": {
                "playbook": playbook_chunks,
                "books": book_chunks,
                "total": playbook_chunks + book_chunks,
            },
            "executions": {
                "total": total_execs,
                "grounded": grounded_execs,
                "grounded_pct": round(grounded_execs / total_execs * 100, 1) if total_execs else 0.0,
            },
            "recent_intent_distribution": intent_counts,
        }
    except Exception as exc:
        return {"status": "degraded", "error": str(exc)}