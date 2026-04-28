from time import perf_counter
from typing import Any, Callable, Dict

def timed_node(name: str, node_fn: Callable[[Dict[str, Any]], Dict[str, Any]], state: Dict[str, Any]) -> Dict[str, Any]:
    start = perf_counter()
    updates = node_fn(state)
    elapsed_ms = round((perf_counter() - start) * 1000, 3)

    state.setdefault('trace', []).append({
        'node': name,
        'elapsed_ms': elapsed_ms
    })
    state.update(updates)
    return state