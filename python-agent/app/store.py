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


def ensure_indexes() -> None:
    documents_collection().create_index([("title", TEXT), ("content", TEXT), ("domain", TEXT)])
    chunks_collection().create_index([("title", TEXT), ("text", TEXT), ("domain", TEXT)])
    executions_collection().create_index("createdAt")
    eval_runs_collection().create_index("createdAt")


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

    documents_collection().delete_many({})
    chunks_collection().delete_many({})
    documents_collection().insert_many(docs)
    chunks_collection().insert_many(chunks)

    return len(docs)


def load_chunks_without_embeddings() -> List[Dict[str, Any]]:
    return list(chunks_collection().find({"embedding": None}))


def set_chunk_embedding(chunk_id: Any, embedding: List[float]) -> None:
    chunks_collection().update_one(
        {"_id": chunk_id},
        {"$set": {"embedding": embedding}},
    )


def all_embedded_chunks() -> List[Dict[str, Any]]:
    return list(chunks_collection().find({"embedding": {"$type": "array"}}))


def save_execution(payload: Dict[str, Any]) -> str:
    doc = {**payload, "createdAt": datetime.now(timezone.utc)}
    result = executions_collection().insert_one(doc)
    return str(result.inserted_id)


def save_eval_run(payload: Dict[str, Any]) -> str:
    doc = {**payload, "createdAt": datetime.now(timezone.utc)}
    result = eval_runs_collection().insert_one(doc)
    return str(result.inserted_id)
