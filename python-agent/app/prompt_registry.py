import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable
@dataclass(frozen=True)
class PromptDefinition:
    name: str
    version: str
    description: str
    template: str
class PromptRegistry:
    def __init__(self, prompts: Dict[str, PromptDefinition]): self._prompts = prompts
    def names(self) -> Iterable[str]: return self._prompts.keys()
    def get(self, name: str) -> PromptDefinition:
        if name not in self._prompts: raise KeyError(f'Prompt not found: {name}')
        return self._prompts[name]
    def version_map(self) -> Dict[str, str]: return {k: v.version for k, v in self._prompts.items()}
    def render(self, name: str, variables: Dict[str, str]) -> str: return self.get(name).template.format_map(_SafeDict(variables))
class _SafeDict(dict):
    def __missing__(self, key): return '{' + key + '}'
def load_prompt_registry(base_dir: Path | None = None) -> PromptRegistry:
    prompt_dir = base_dir or Path(__file__).parent / 'prompts'; prompts: Dict[str, PromptDefinition] = {}
    for file in sorted(prompt_dir.glob('*.json')):
        data = json.loads(file.read_text(encoding='utf-8'))
        prompts[data['name']] = PromptDefinition(name=data['name'], version=data['version'], description=data.get('description', ''), template=data['template'])
    return PromptRegistry(prompts)
_registry = None
def default_prompt_registry() -> PromptRegistry:
    global _registry
    if _registry is None: _registry = load_prompt_registry()
    return _registry