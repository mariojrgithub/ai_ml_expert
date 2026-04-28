from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

Intent = Literal["QA", "CODE", "SQL", "MONGO"]
UiFormat = Literal["markdown", "code", "json", "text"]


class ChatRequest(BaseModel):
    sessionId: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    executionId: str
    intent: Intent
    format: UiFormat = "markdown"
    content: Any
    language: Optional[str] = None
    warnings: List[str] = []
    citations: List[Dict[str, Any]] = []