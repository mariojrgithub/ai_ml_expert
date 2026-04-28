from typing import Any, Dict, List, Literal
from pydantic import BaseModel, Field

Intent = Literal['QA', 'CODE', 'SQL', 'MONGO']

class ChatRequest(BaseModel):
    sessionId: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)

class ChatResponse(BaseModel):
    executionId: str
    intent: Intent
    answer: str
    warnings: List[str] = []
    citations: List[Dict[str, Any]] = []