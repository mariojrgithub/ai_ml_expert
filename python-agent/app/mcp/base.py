from abc import ABC, abstractmethod
from typing import Dict, List


class WebSearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 3) -> List[Dict]:
        raise NotImplementedError