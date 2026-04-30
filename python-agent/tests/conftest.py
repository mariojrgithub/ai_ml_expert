"""
pytest conftest.py — shared stubs for Docker-only packages.

This runs before any test module is collected, ensuring all stub
sys.modules entries are set once. Using setdefault means already-imported
real packages (e.g. pydantic_settings if installed) are never replaced.

pydantic_settings is stubbed with a real class so that app.config.Settings
inherits from it and initialises correctly (otherwise settings attributes
become MagicMock objects, breaking numeric comparisons in checker.py).
"""
import sys
from unittest.mock import MagicMock


class _BaseSettingsStub:
    """Minimal BaseSettings replacement: reads class-level defaults only."""
    def __init__(self, **kwargs):
        # Apply class-level field defaults if not already set as instance attrs
        for cls in type(self).__mro__:
            for k, v in vars(cls).items():
                if k.startswith("_") or callable(v) or isinstance(v, (classmethod, staticmethod, property)):
                    continue
                if not hasattr(self, k) or isinstance(getattr(self, k), type(v)):
                    object.__setattr__(self, k, v)
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)

    class model_config:
        env_file = ".env"
        extra = "ignore"


_pydantic_settings_stub = MagicMock()
_pydantic_settings_stub.BaseSettings = _BaseSettingsStub

sys.modules.setdefault("pymongo", MagicMock())
sys.modules.setdefault("pymongo.collection", MagicMock())
sys.modules.setdefault("pymongo.errors", MagicMock())
sys.modules.setdefault("pydantic_settings", _pydantic_settings_stub)
sys.modules.setdefault("langchain_ollama", MagicMock())
