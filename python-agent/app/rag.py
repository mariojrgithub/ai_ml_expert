from math import sqrt
from typing import Dict, List, Tuple
from .llm import embedding_model
from .store import all_embedded_chunks, load_chunks_without_embeddings, set_chunk_embedding

def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b): return -1.0
    dot = sum(x * y for x, y in zip(a, b)); norm_a = sqrt(sum(x * x for x in a)); norm_b = sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0: return -1.0
    return dot / (norm_a * norm_b)

def reindex_embeddings() -> int:
    model = embedding_model(); chunks = load_chunks_without_embeddings(); count = 0
    for chunk in chunks:
        set_chunk_embedding(chunk['_id'], model.embed_query(chunk['text'])); count += 1
    return count

def _keyword_overlap_score(question: str, text: str) -> float:
    q_tokens = {t for t in question.lower().split() if len(t) > 2}
    t_tokens = {t for t in text.lower().split() if len(t) > 2}
    if not q_tokens: return 0.0
    return len(q_tokens & t_tokens) / max(len(q_tokens), 1)

def _domain_bonus(question: str, domain: str | None) -> float:
    q = question.lower()
    if not domain: return 0.0
    if domain in q: return 0.15
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

def retrieve_context(question: str, limit: int = 4) -> List[Dict]:
    chunks = all_embedded_chunks()
    if not chunks: return []
    qv = embedding_model().embed_query(question); scored = []
    for chunk in chunks:
        enriched = dict(chunk); enriched['similarity'] = cosine_similarity(qv, chunk.get('embedding', [])); scored.append(enriched)
    scored.sort(key=lambda x: x.get('similarity', -1.0), reverse=True)
    top_semantic = scored[:max(limit * 2, 6)]
    return rerank_docs(question, top_semantic, limit=limit)

def context_to_text(docs: List[Dict]) -> str:
    if not docs: return 'No internal context found.'
    return '\n\n'.join(f"Title: {d.get('title')}\nDomain: {d.get('domain')}\nSource: {d.get('source')}\nSimilarity: {round(d.get('similarity', 0.0), 4)}\nRerank: {round(d.get('rerank_score', 0.0), 4)}\nText: {d.get('text')}" for d in docs)