from typing import Any, Dict
import logging
import os
import secrets
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from starlette.concurrency import iterate_in_threadpool
from .agent_runtime import run_agent_with_trace, stream_agent_tokens
from .llm import code_llm, embedding_model, general_llm
from .models import ChatRequest, ChatResponse
from .prompt_registry import default_prompt_registry
from .sanitizer import PromptInjectionError, sanitize_user_input
from .rag import invalidate_chunk_cache, reindex_embeddings
from .store import (
    ensure_indexes, save_execution, seed_sample_documents,
    chunks_collection, book_chunks_collection, executions_collection,
    get_health_detail,
)
from .evals.runner import run_all_evals
from .evals.reporting import list_report_files
import json
from fastapi.responses import StreamingResponse


app = FastAPI(title='Engineering Copilot Agent', version='0.0.6')

log = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Admin API-key auth
# The ADMIN_API_KEY env var must be set; the service will reject any
# request to /admin/* that does not supply it in the X-Admin-Api-Key
# header.
# -------------------------------------------------------------------
_ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")
_admin_key_header = APIKeyHeader(name="X-Admin-Api-Key", auto_error=False)


def require_admin_key(api_key: str | None = Security(_admin_key_header)) -> None:
    if not _ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_API_KEY is not configured on this server.",
        )
    if not api_key or not secrets.compare_digest(api_key, _ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Api-Key header.",
        )

_DOMAIN_TO_LANGUAGE: Dict[str, str] = {
    "java":          "java",
    "python":        "python",
    "deep_learning": "python",
    "data_science":  "python",
    "algorithms":    "python",
    "security":      "python",
    "finance":       "python",
    "ml":            "python",
    "platform":      "python",
    "sql":           "sql",
    "mongodb":       "javascript",
    "code":          "python",
}

_INTENT_TO_FORMAT: Dict[str, str] = {
    "CODE": "code",
    "SQL": "code",
    "MONGO": "code",
    "QA": "markdown",
}

def resolve_format_and_language(intent: str, domain: str | None):
    fmt = _INTENT_TO_FORMAT.get(intent, "markdown")
    language = _DOMAIN_TO_LANGUAGE.get(domain or "", None) if fmt == "code" else None
    return fmt, language

_PLACEHOLDER_PREFIX = "CHANGE_ME"

@app.on_event('startup')
def startup() -> None:
    if not _ADMIN_API_KEY:
        raise RuntimeError("ADMIN_API_KEY environment variable is not set. Set it before starting the service.")
    if _ADMIN_API_KEY.startswith(_PLACEHOLDER_PREFIX):
        raise RuntimeError("ADMIN_API_KEY is still set to the example placeholder. Generate a real secret with: openssl rand -hex 32")
    ensure_indexes()
    # Pre-warm LLM and embedding model singletons so the first request has no cold-start delay.
    general_llm()
    code_llm()
    embedding_model()
@app.get('/health')
def health() -> Dict[str, str]: return {'status': 'ok'}
@app.get('/admin/prompts')
def list_prompts(_: None = Depends(require_admin_key)) -> Dict[str, Any]:
    registry = default_prompt_registry(); return {'prompts': list(registry.names()), 'versions': registry.version_map()}
@app.post('/admin/seed')
def seed(_: None = Depends(require_admin_key)) -> Dict[str, Any]: return {'seeded_documents': seed_sample_documents()}
@app.post('/admin/reindex')
def reindex(_: None = Depends(require_admin_key)) -> Dict[str, Any]:
    count = reindex_embeddings()
    invalidate_chunk_cache()
    return {'embedded_chunks': count}
@app.post('/admin/evals/run')
def run_evals(background_tasks: BackgroundTasks, _: None = Depends(require_admin_key)) -> Dict[str, Any]:
    background_tasks.add_task(run_all_evals)
    return {'status': 'running', 'message': 'Eval run started in the background. Check GET /admin/evals/reports for results.'}
@app.get('/admin/evals/reports')
def eval_reports(_: None = Depends(require_admin_key)) -> Dict[str, Any]: return {'reports': list_report_files()}

@app.get('/admin/health/detail')
def health_detail(_: None = Depends(require_admin_key)) -> Dict[str, Any]:
    """Operational dashboard — chunk counts and recent execution stats."""
    return get_health_detail()

@app.post("/agent/chat", response_model=ChatResponse)
def chat(request: ChatRequest, x_correlation_id: str | None = Header(default=None)) -> ChatResponse:
    cid = x_correlation_id or secrets.token_hex(8)
    log.info("[%s] POST /agent/chat sessionId=%s", cid, request.sessionId)
    try:
        sanitized_message, _ = sanitize_user_input(request.message)
    except PromptInjectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    result = run_agent_with_trace(
        session_id=request.sessionId,
        user_input=sanitized_message,
    )

    answer = str(result.get("final_answer") or "")
    intent = result.get("intent", "QA")
    domain = result.get("domain")
    warnings = result.get("warnings", [])
    citations = result.get("citations", [])

    fmt, language = resolve_format_and_language(intent, domain)

    execution_id = save_execution({
        "sessionId": request.sessionId,
        "intent": intent,
        "domain": domain,
        "answer": answer,
        "format": fmt,
        "language": language,
        "warnings": warnings,
        "citations": citations,
        "grounded": result.get("grounded", False),
        "trace": result.get("trace", []),
    })

    meta = result.get("run_metadata", {})
    return ChatResponse(
        executionId=execution_id,
        intent=intent,
        format=fmt,
        content=answer,
        language=language,
        warnings=warnings,
        citations=citations,
        abstain=meta.get("abstain", False),
        groundedness_score=float(meta.get("groundedness_score", 0.0)),
        relevance_score=float(meta.get("relevance_score", 0.0)),
    )


@app.post("/agent/chat/stream")
async def chat_stream(request: ChatRequest, x_correlation_id: str | None = Header(default=None)):
    """
    Streams JSON lines (NDJSON).
    Each line is a self-contained JSON object:
      {"type": "meta",  "format": ..., "language": ..., "intent": ..., "executionId": ...}
      {"type": "delta", "content": "<token>"}  — one per LLM token
      {"type": "done",  "warnings": [...], "citations": [...]}
      {"type": "error", "message": "..."}      — on stream failure
    """
    try:
        sanitized_message, _ = sanitize_user_input(request.message)
    except PromptInjectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    cid = x_correlation_id or secrets.token_hex(8)
    log.info("[%s] POST /agent/chat/stream sessionId=%s", cid, request.sessionId)

    def generator():
        meta_sent = False
        fmt = "markdown"
        language = None
        intent = "QA"
        execution_id = None

        try:
            for event in stream_agent_tokens(
                session_id=request.sessionId,
                user_input=sanitized_message,
            ):
                if event["type"] == "pre":
                    state = event["state"]
                    intent = state.get("intent", "QA")
                    domain = state.get("domain")
                    fmt, language = resolve_format_and_language(intent, domain)
                    yield json.dumps({
                        "type": "meta",
                        "format": fmt,
                        "language": language,
                        "intent": intent,
                        "executionId": None,
                    }) + "\n"
                    meta_sent = True

                elif event["type"] == "token":
                    yield json.dumps({
                        "type": "delta",
                        "content": event["content"],
                    }) + "\n"

                elif event["type"] == "post":
                    state = event["state"]
                    answer = str(state.get("final_answer") or "")
                    warnings = state.get("warnings", [])
                    citations = state.get("citations", [])
                    run_meta = state.get("run_metadata", {})
                    execution_id = save_execution({
                        "sessionId": request.sessionId,
                        "intent": intent,
                        "domain": state.get("domain"),
                        "answer": answer,
                        "format": fmt,
                        "language": language,
                        "warnings": warnings,
                        "citations": citations,
                        "grounded": state.get("grounded", False),
                        "trace": state.get("trace", []),
                    })
                    yield json.dumps({
                        "type": "done",
                        "executionId": execution_id,
                        "warnings": warnings,
                        "citations": citations,
                        "abstain": bool(run_meta.get("abstain", False)),
                        "groundedness_score": float(run_meta.get("groundedness_score", 0.0)),
                        "relevance_score": float(run_meta.get("relevance_score", 0.0)),
                    }) + "\n"
        except Exception as exc:
            if not meta_sent:
                yield json.dumps({
                    "type": "meta",
                    "format": fmt,
                    "language": language,
                    "intent": intent,
                    "executionId": execution_id,
                }) + "\n"
            yield json.dumps({
                "type": "error",
                "message": f"stream failed: {exc}",
            }) + "\n"

    return StreamingResponse(
        iterate_in_threadpool(generator()),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
