from typing import List, Tuple

def validate_sql(text: str) -> Tuple[str, List[str]]:
    warnings = []
    normalized = text.strip().lower()
    if any(token in normalized for token in ['delete ', 'update ', 'insert ', 'drop ', 'truncate ']):
        warnings.append('Potentially destructive SQL detected; keep outputs read-only.')
    if 'select' not in normalized:
        warnings.append('SQL output may not be a SELECT statement.')
    return text, warnings

def validate_mongo(text: str) -> Tuple[str, List[str]]:
    warnings = []
    normalized = text.lower()
    if '$where' in normalized:
        warnings.append('Unsafe MongoDB operator $where detected.')
    if any(token in normalized for token in ['delete', 'update', 'remove', 'drop']):
        warnings.append('Potentially destructive MongoDB operation detected; keep outputs read-only.')
    return text, warnings

def validate_code(text: str, language: str) -> Tuple[str, List[str]]:
    warnings = []
    if language == 'java' and 'class ' not in text:
        warnings.append('Java output may be incomplete; no class declaration found.')
    if language == 'python' and 'def ' not in text and 'class ' not in text:
        warnings.append('Python output may be incomplete; no function or class declaration found.')
    return text, warnings