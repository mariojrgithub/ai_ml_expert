import pytest
from pathlib import Path
from app.prompt_registry import load_prompt_registry, PromptRegistry, PromptDefinition, _SafeDict


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

def _registry():
    return load_prompt_registry(Path("app/prompts"))


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def test_prompt_registry_loads_json_prompts():
    registry = _registry()
    assert registry.get("qa").version == "1.5.0"


def test_prompt_registry_loads_all_ten_prompts():
    registry = _registry()
    names = list(registry.names())
    assert len(names) == 10


def test_prompt_registry_version_map_has_all_prompts():
    registry = _registry()
    vm = registry.version_map()
    assert "qa" in vm
    assert "sql" in vm
    assert "mongo" in vm
    assert vm["qa"] == "1.5.0"


def test_prompt_registry_raises_on_unknown_name():
    registry = _registry()
    with pytest.raises(KeyError, match="no_such_prompt"):
        registry.get("no_such_prompt")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def test_render_substitutes_known_variable():
    defn = PromptDefinition(name="t", version="0", description="", template="Hello {name}!")
    registry = PromptRegistry({"t": defn})
    assert registry.render("t", {"name": "World"}) == "Hello World!"


def test_render_leaves_unknown_slots_intact():
    """_SafeDict must not raise on missing keys — it re-inserts the placeholder."""
    defn = PromptDefinition(name="t", version="0", description="", template="Q: {question} C: {context}")
    registry = PromptRegistry({"t": defn})
    result = registry.render("t", {"question": "hi"})
    assert "{context}" in result
    assert "hi" in result


def test_render_multiple_slots():
    defn = PromptDefinition(name="t", version="0", description="", template="{a} + {b} = {c}")
    registry = PromptRegistry({"t": defn})
    assert registry.render("t", {"a": "1", "b": "2", "c": "3"}) == "1 + 2 = 3"


# ---------------------------------------------------------------------------
# _SafeDict
# ---------------------------------------------------------------------------

def test_safedict_returns_placeholder_for_missing_key():
    d = _SafeDict({"x": "10"})
    assert d["x"] == "10"
    assert d["missing"] == "{missing}"


def test_safedict_works_with_format_map():
    result = "{a} {b} {c}".format_map(_SafeDict({"a": "hello"}))
    assert result == "hello {b} {c}"