from app.evals.reporting import build_report_artifacts


def test_build_report_artifacts_creates_paths():
    artifacts = build_report_artifacts(
        {
            "summary": {"pass_rate": 1.0},
            "results": [],
        }
    )
    assert artifacts["json_report"].endswith(".json")
    assert artifacts["html_report"].endswith(".html")