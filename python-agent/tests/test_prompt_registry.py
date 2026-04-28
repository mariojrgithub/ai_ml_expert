from pathlib import Path
from app.prompt_registry import load_prompt_registry


def test_prompt_registry_loads_json_prompts():
    registry = load_prompt_registry(Path("app/prompts"))
    assert registry.get("qa").version == "1.1.0"