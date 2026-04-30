from app.evals.reporting import build_report_artifacts


def test_build_report_artifacts_creates_paths():
    artifacts = build_report_artifacts(
        {
            "summary": {"pass_rate": 1.0, "passed_cases": 1, "total_cases": 1,
                        "avg_relevance_score": 0.75, "avg_groundedness_score": 0.60,
                        "abstain_count": 0},
            "results": [],
        }
    )
    assert artifacts["json_report"].endswith(".json")
    assert artifacts["html_report"].endswith(".html")


def test_build_report_html_contains_new_columns():
    import pathlib
    artifacts = build_report_artifacts(
        {
            "summary": {"pass_rate": 0.5, "passed_cases": 1, "total_cases": 2,
                        "avg_relevance_score": 0.80, "avg_groundedness_score": 0.55,
                        "abstain_count": 1},
            "results": [
                {
                    "id": "qa-001",
                    "task_type": "QA",
                    "score": {
                        "passed": True,
                        "failure_category": "none",
                        "required_hits": ["python"],
                        "forbidden_hits": [],
                        "relevance_score": 0.82,
                        "groundedness_score": 0.61,
                        "abstain": False,
                    },
                },
            ],
        }
    )
    html_content = pathlib.Path(artifacts["html_report"]).read_text(encoding="utf-8")
    # New columns present in header
    assert "Relevance" in html_content
    assert "Groundedness" in html_content
    assert "Abstain" in html_content
    # Summary stats rendered
    assert "0.82" in html_content or "0.80" in html_content
    # Pass indicator colour-coded
    assert "PASS" in html_content
