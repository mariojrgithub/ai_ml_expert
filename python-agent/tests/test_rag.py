"""Tests for app.rag — similarity threshold and rerank logic.

Docker-only packages (pymongo, pydantic_settings, langchain_ollama) are
stubbed by conftest.py, so the module-level imports in rag.py succeed.
retrieve_context is NOT tested here because it calls embedding_model()
which requires Ollama. We test the pure functions instead.
"""
from unittest.mock import patch, MagicMock

from app.rag import (
    cosine_similarity,
    rerank_docs,
    _keyword_overlap_score,
    _domain_bonus,
    retrieve_context,
    invalidate_chunk_cache,
    _get_cached_chunks,
)


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------

def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert cosine_similarity(v, v) == 1.0


def test_cosine_similarity_orthogonal_vectors():
    score = cosine_similarity([1.0, 0.0], [0.0, 1.0])
    assert score == 0.0


def test_cosine_similarity_empty_vectors_returns_minus_one():
    assert cosine_similarity([], []) == -1.0


def test_cosine_similarity_mismatched_lengths_returns_minus_one():
    assert cosine_similarity([1.0], [1.0, 2.0]) == -1.0


# ---------------------------------------------------------------------------
# _keyword_overlap_score
# ---------------------------------------------------------------------------

def test_keyword_overlap_full_match():
    score = _keyword_overlap_score("unit tests pipeline", "unit tests pipeline")
    assert score == 1.0


def test_keyword_overlap_no_match():
    score = _keyword_overlap_score("docker kubernetes", "pandas numpy dataframe")
    assert score == 0.0


def test_keyword_overlap_partial_match():
    score = _keyword_overlap_score("python unit tests pipeline", "unit tests run")
    assert 0.0 < score < 1.0


# ---------------------------------------------------------------------------
# _domain_bonus
# ---------------------------------------------------------------------------

def test_domain_bonus_multi_keyword_match():
    # "java" domain; question mentions both "java" and "spring"
    bonus = _domain_bonus("write a java spring boot controller", "java")
    assert bonus == 0.20


def test_domain_bonus_single_keyword_match():
    bonus = _domain_bonus("write a java REST endpoint", "java")
    assert bonus == 0.12


def test_domain_bonus_no_match():
    bonus = _domain_bonus("how do I bake bread", "java")
    assert bonus == 0.0


def test_domain_bonus_general_domain_returns_zero():
    bonus = _domain_bonus("anything", "general")
    assert bonus == 0.0


# ---------------------------------------------------------------------------
# rerank_docs — similarity threshold behaviour
# ---------------------------------------------------------------------------

def _make_docs(*sims):
    return [{"text": f"doc {s}", "domain": "general", "similarity": s} for s in sims]


def test_rerank_docs_orders_by_combined_score():
    docs = _make_docs(0.9, 0.5, 0.3)
    ranked = rerank_docs("test question", docs, limit=3)
    scores = [d["rerank_score"] for d in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rerank_docs_respects_limit():
    docs = _make_docs(0.9, 0.8, 0.7, 0.6, 0.5)
    ranked = rerank_docs("test question", docs, limit=2)
    assert len(ranked) == 2


def test_rerank_docs_empty_input():
    assert rerank_docs("question", [], limit=4) == []


# ---------------------------------------------------------------------------
# retrieve_context — min_similarity threshold filter
# ---------------------------------------------------------------------------

def test_retrieve_context_filters_below_threshold():
    """Docs below min_similarity must not reach reranking."""
    fake_chunks = [
        {"text": "high quality doc", "domain": "general", "embedding": [1.0, 0.0]},
        {"text": "low quality doc",  "domain": "general", "embedding": [0.0, 1.0]},
    ]
    # question embedding points toward [1, 0], so first doc ~1.0 sim, second ~0.0
    with patch("app.rag._get_cached_chunks", return_value=fake_chunks), \
         patch("app.rag.embedding_model") as mock_em:
        mock_em.return_value.embed_query.return_value = [1.0, 0.0]
        # threshold 0.5 — only the first doc should survive
        results = retrieve_context("test question", limit=4, min_similarity=0.5)

    assert all(d["similarity"] >= 0.5 for d in results)
    texts = [d["text"] for d in results]
    assert "high quality doc" in texts
    assert "low quality doc" not in texts


def test_retrieve_context_returns_empty_when_all_below_threshold():
    fake_chunks = [
        {"text": "irrelevant doc", "domain": "general", "embedding": [0.0, 1.0]},
    ]
    with patch("app.rag._get_cached_chunks", return_value=fake_chunks), \
         patch("app.rag.embedding_model") as mock_em:
        mock_em.return_value.embed_query.return_value = [1.0, 0.0]
        results = retrieve_context("test question", limit=4, min_similarity=0.9)

    assert results == []


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------

def test_invalidate_chunk_cache_forces_refresh():
    """After invalidate, _get_cached_chunks must call the store again."""
    invalidate_chunk_cache()
    fake = [{"text": "fresh", "domain": "g", "embedding": []}]
    with patch("app.rag.all_embedded_chunks", return_value=fake) as mock_store:
        result = _get_cached_chunks()
    mock_store.assert_called_once()
    assert result == fake
