from app.rag import rerank_docs


def test_rerank_docs_prefers_keyword_overlap():
    docs = [
        {
            "text": "unit tests integration tests pipeline",
            "domain": "cicd",
            "similarity": 0.6,
        },
        {
            "text": "random unrelated content",
            "domain": "misc",
            "similarity": 0.61,
        },
    ]

    ranked = rerank_docs(
        "What are the CI/CD unit tests guardrails?",
        docs,
        limit=2,
    )
    assert ranked[0]["text"] == "unit tests integration tests pipeline"