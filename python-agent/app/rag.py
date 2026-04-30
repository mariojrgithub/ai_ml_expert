from math import sqrt
from time import monotonic
from typing import Dict, List, Optional, Tuple
from .config import settings
from .llm import embedding_model
from .store import all_embedded_chunks, load_chunks_without_embeddings, set_chunk_embedding

# Hard character cap applied before every Ollama embed_query call.
_MAX_EMBED_CHARS = 1200

# ---------------------------------------------------------------------------
# In-memory chunk cache with TTL to avoid a full collection scan per request.
# ---------------------------------------------------------------------------
_chunk_cache: Optional[List[Dict]] = None
_chunk_cache_ts: float = 0.0
_CHUNK_CACHE_TTL_SECONDS = 120.0


def _get_cached_chunks() -> List[Dict]:
    global _chunk_cache, _chunk_cache_ts
    if _chunk_cache is None or (monotonic() - _chunk_cache_ts) > _CHUNK_CACHE_TTL_SECONDS:
        _chunk_cache = all_embedded_chunks()
        _chunk_cache_ts = monotonic()
    return _chunk_cache


def invalidate_chunk_cache() -> None:
    """Call after reindex to force a fresh load on the next request."""
    global _chunk_cache
    _chunk_cache = None

# Keyword sets used by _domain_bonus() to score chunk relevance.
# Multi-keyword matches score higher than single matches.
_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "java":          ["java", "spring", "jvm", "maven", "gradle", "junit"],
    "python":        ["python", "pip", "venv", "pytest"],
    "deep_learning": ["pytorch", "tensorflow", "keras", "neural network", "deep learning",
                      "cnn", "rnn", "lstm", "transformer", "backprop", "epoch", "gradient"],
    "data_science":  ["pandas", "numpy", "dataframe", "matplotlib", "seaborn",
                      "sklearn", "scikit", "data analysis", "data science"],
    "algorithms":    ["algorithm", "data structure", "sorting", "graph", "tree",
                      "binary search", "big o", "complexity", "dynamic programming"],
    "security":      ["security", "hacking", "exploit", "vulnerability", "encryption",
                      "cipher", "penetration", "ctf", "malware"],
    "finance":       ["finance", "trading", "portfolio", "quant", "stock",
                      "derivative", "option", "risk", "bond", "volatility"],
    "ml":            ["machine learning", "bayesian", "linear algebra", "matrix",
                      "regression", "classification", "clustering", "probability"],
    "platform":      ["platform", "devops", "kubernetes", "docker", "infrastructure",
                      "aws", "cloud", "helm", "ci/cd"],
    "sql":           ["sql", "select", "database", "schema", "join", "query"],
    "mongodb":       ["mongodb", "mongo", "aggregate", "document", "collection"],
}

def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b): return -1.0
    dot = sum(x * y for x, y in zip(a, b)); norm_a = sqrt(sum(x * x for x in a)); norm_b = sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0: return -1.0
    return dot / (norm_a * norm_b)

def reindex_embeddings() -> int:
    model = embedding_model(); chunks = load_chunks_without_embeddings(); count = 0
    for chunk in chunks:
        text = chunk['text'][:_MAX_EMBED_CHARS]
        set_chunk_embedding(chunk['_id'], model.embed_query(text)); count += 1
    return count

def _keyword_overlap_score(question: str, text: str) -> float:
    q_tokens = {t for t in question.lower().split() if len(t) > 2}
    t_tokens = {t for t in text.lower().split() if len(t) > 2}
    if not q_tokens: return 0.0
    return len(q_tokens & t_tokens) / max(len(q_tokens), 1)

def _domain_bonus(question: str, domain: str | None) -> float:
    """Score based on how many domain keywords appear in the question.
    Multi-keyword matches produce a higher bonus than single matches,
    rewarding chunks whose domain closely matches the query topic.
    """
    if not domain or domain in ("general", "code"):
        return 0.0
    keywords = _DOMAIN_KEYWORDS.get(domain, [domain])
    q = question.lower()
    matches = sum(1 for kw in keywords if kw in q)
    if matches >= 2:
        return 0.20
    if matches == 1:
        return 0.12
    return 0.0

def rerank_docs(question: str, docs: List[Dict], limit: int = 4) -> List[Dict]:
    reranked = []
    for d in docs:
        semantic = d.get('similarity', 0.0)
        overlap = _keyword_overlap_score(question, d.get('text', ''))
        bonus = _domain_bonus(question, d.get('domain'))
        score = round((semantic * 0.7) + (overlap * 0.25) + bonus, 6)
        enriched = dict(d); enriched['rerank_score'] = score; reranked.append(enriched)
    reranked.sort(key=lambda x: x.get('rerank_score', -1.0), reverse=True)
    return reranked[:limit]

def retrieve_context(question: str, limit: int = 4,
                     min_similarity: Optional[float] = None) -> List[Dict]:
    threshold = min_similarity if min_similarity is not None else settings.min_retrieval_similarity
    chunks = _get_cached_chunks()
    if not chunks: return []
    qv = embedding_model().embed_query(question[:_MAX_EMBED_CHARS]); scored = []
    for chunk in chunks:
        enriched = dict(chunk)
        enriched['similarity'] = cosine_similarity(qv, chunk.get('embedding', []))
        scored.append(enriched)
    # Apply minimum similarity threshold before reranking to prevent low-quality
    # docs from reaching the LLM.
    above_threshold = [d for d in scored if d.get('similarity', -1.0) >= threshold]
    above_threshold.sort(key=lambda x: x.get('similarity', -1.0), reverse=True)
    top_semantic = above_threshold[:max(limit * 2, 6)]
    return rerank_docs(question, top_semantic, limit=limit)

def context_to_text(docs: List[Dict]) -> str:
    if not docs: return 'No internal context found.'
    return '\n\n'.join(f"Title: {d.get('title')}\nDomain: {d.get('domain')}\nSource: {d.get('source')}\nText: {d.get('text')}" for d in docs)