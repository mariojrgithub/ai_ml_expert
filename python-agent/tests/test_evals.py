from app.evals.runner import score_case


def test_score_case_flags_forbidden_present():
    result = score_case(
        "select * from x; drop table y;",
        [],
        {
            "required_keywords": ["select"],
            "forbidden_keywords": ["drop table"],
        },
        {"grounded": True},
    )
    assert result["failure_category"] == "forbidden_present"