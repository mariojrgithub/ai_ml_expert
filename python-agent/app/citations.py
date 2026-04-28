from typing import Dict, List

def format_citations(citations: List[Dict], max_items: int = 3) -> str:
    if not citations:
        return ''
    parts = []
    for c in citations[:max_items]:
        title = c.get('title', 'unknown')
        source = c.get('source', 'unknown')
        parts.append(f"[{title} | {source}]")
    return ' Sources: ' + '; '.join(parts)