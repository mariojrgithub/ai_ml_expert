from typing import Any, Dict
from fastapi import BackgroundTasks, FastAPI
from .agent_runtime import run_agent_with_trace, stream_agent_tokens
from .models import ChatRequest, ChatResponse
from .prompt_registry import default_prompt_registry
from .rag import reindex_embeddings
from .store import ensure_indexes, save_execution, seed_sample_documents
from .evals.runner import run_all_evals
from .evals.reporting import list_report_files
import json
from fastapi.responses import StreamingResponse


app = FastAPI(title='Engineering Copilot Agent', version='0.0.6')

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
def run_evals(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    background_tasks.add_task(run_all_evals)
    return {'status': 'running', 'message': 'Eval run started in the background. Check GET /admin/evals/reports for results.'}
@app.get('/admin/evals/reports')
def eval_reports() -> Dict[str, Any]: return {'reports': list_report_files()}

@app.post("/agent/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    result = run_agent_with_trace(
        session_id=request.sessionId,
        user_input=request.message,
    )

    answer = str(result.get("validated_output") or "")
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
    Each line is a self-contained JSON object:
      {"type": "meta",  "format": ..., "language": ..., "intent": ..., "executionId": ...}
      {"type": "delta", "content": "<token>"}  — one per LLM token
      {"type": "done",  "warnings": [...], "citations": [...]}
    """

    def generator():
        meta_sent = False
        fmt = "markdown"
        language = None
        intent = "QA"
        execution_id = None

        for event in stream_agent_tokens(
            session_id=request.sessionId,
            user_input=request.message,
        ):
            if event['type'] == 'pre':
                state = event['state']
                intent = state.get('intent', 'QA')
                domain = state.get('domain')
                fmt, language = resolve_format_and_language(intent, domain)
                # executionId is not yet known — placeholder; updated after 'post'
                yield json.dumps({
                    "type": "meta",
                    "format": fmt,
                    "language": language,
                    "intent": intent,
                    "executionId": None,
                }) + "\n"
                meta_sent = True

            elif event['type'] == 'token':
                yield json.dumps({
                    "type": "delta",
                    "content": event['content'],
                }) + "\n"

            elif event['type'] == 'post':
                state = event['state']
                answer = str(state.get('validated_output') or "")
                warnings = state.get('warnings', [])
                citations = state.get('citations', [])
                execution_id = save_execution({
                    "sessionId": request.sessionId,
                    "intent": intent,
                    "domain": state.get('domain'),
                    "answer": answer,
                    "format": fmt,
                    "language": language,
                    "warnings": warnings,
                    "citations": citations,
                })
                yield json.dumps({
                    "type": "done",
                    "executionId": execution_id,
                    "warnings": warnings,
                    "citations": citations,
                }) + "\n"

    return StreamingResponse(
        generator(),
        media_type="application/x-ndjson",
    )

