from typing import Any, Dict
from fastapi import FastAPI
from .agent_runtime import run_agent_with_trace
from .models import ChatRequest, ChatResponse
from .prompt_registry import default_prompt_registry
from .rag import reindex_embeddings
from .store import ensure_indexes, save_execution, seed_sample_documents
from .evals.runner import run_all_evals
from .evals.reporting import list_report_files
import json
from fastapi.responses import StreamingResponse


app = FastAPI(title='Engineering Copilot Agent', version='0.0.6')

def infer_ui_format(intent: str, content: str):
    if intent == "CODE":
        if "class " in content or "@RestController" in content:
            return "code", "java"
        return "code", "python"

    if intent == "SQL":
        return "code", "sql"

    if intent == "MONGO":
        return "code", "javascript"

    if content.strip().startswith("{") or content.strip().startswith("["):
        try:
            json.loads(content)
            return "json", None
        except Exception:
            pass

    return "markdown", None

def chunk_for_stream(text: str, size: int = 32):
    for i in range(0, len(text), size):
        yield text[i : i + size]

@app.on_event('startup')
def startup() -> None: ensure_indexes()
@app.get('/health')
def health() -> Dict[str, str]: return {'status': 'ok'}
@app.get('/admin/prompts')
def list_prompts() -> Dict[str, Any]:
    registry = default_prompt_registry(); return {'prompts': list(registry.names()), 'versions': registry.version_map()}
@app.post('/admin/seed')
def seed() -> Dict[str, Any]: return {'seeded_documents': seed_sample_documents()}
@app.post('/admin/reindex')
def reindex() -> Dict[str, Any]: return {'embedded_chunks': reindex_embeddings()}
@app.post('/admin/evals/run')
def run_evals() -> Dict[str, Any]: return run_all_evals()
@app.get('/admin/evals/reports')
def eval_reports() -> Dict[str, Any]: return {'reports': list_report_files()}

@app.post("/agent/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    result = run_agent_with_trace(
        session_id=request.sessionId,
        user_input=request.message,
    )

    answer = result.get("validated_output", "")
    intent = result.get("intent", "QA")
    warnings = result.get("warnings", [])
    citations = result.get("citations", [])

    fmt, language = infer_ui_format(intent, answer)

    execution_id = save_execution({
        "sessionId": request.sessionId,
        "intent": intent,
        "answer": answer,
        "format": fmt,
        "language": language,
        "warnings": warnings,
        "citations": citations,
    })

    return ChatResponse(
        executionId=execution_id,
        intent=intent,
        format=fmt,
        content=answer,
        language=language,
        warnings=warnings,
        citations=citations,
    )


@app.post("/agent/chat/stream")
def chat_stream(request: ChatRequest):
    """
    Streams JSON lines (NDJSON).
    Each line is a self-contained JSON object.
    """

    def generator():
        result = run_agent_with_trace(
            session_id=request.sessionId,
            user_input=request.message,
        )

        answer = result.get("validated_output", "")
        intent = result.get("intent", "QA")
        warnings = result.get("warnings", [])
        citations = result.get("citations", [])

        fmt, language = infer_ui_format(intent, answer)

        execution_id = save_execution({
            "sessionId": request.sessionId,
            "intent": intent,
            "answer": answer,
            "format": fmt,
            "language": language,
            "warnings": warnings,
            "citations": citations,
        })

        # ---- meta ----
        yield json.dumps({
            "type": "meta",
            "format": fmt,
            "language": language,
            "intent": intent,
            "executionId": execution_id,
        }) + "\n"

        # ---- content ----
        for chunk in chunk_for_stream(answer):
            yield json.dumps({
                "type": "delta",
                "content": chunk,
            }) + "\n"

        # ---- done ----
        yield json.dumps({
            "type": "done",
            "warnings": warnings,
            "citations": citations,
        }) + "\n"

    return StreamingResponse(
        generator(),
        media_type="application/x-ndjson",
    )


