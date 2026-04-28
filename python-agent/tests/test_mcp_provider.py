from app.mcp.client import McpWebSearchProvider


def test_normalize_result_from_dict_results():
    provider = McpWebSearchProvider(command="python", args=["-V"])
    result = provider._normalize_result(
        {
            "results": [
                {
                    "title": "A",
                    "snippet": "B",
                    "url": "U",
                }
            ]
        }
    )
    assert result[0]["title"] == "A"