from typing import Any, Dict
from fastapi import FastAPI
from .agent_runtime import run_agent_with_trace
from .models import ChatRequest, ChatResponse
from .prompt_registry import default_prompt_registry
from .rag import reindex_embeddings
from .store import ensure_indexes, save_execution, seed_sample_documents
from .evals.runner import run_all_evals
from .evals.reporting import list_report_files
app = FastAPI(title='Engineering Copilot Agent', version='0.0.6')
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
@app.post('/agent/chat', response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    result = run_agent_with_trace(session_id=request.sessionId, user_input=request.message)
    execution_payload = {'sessionId': request.sessionId, 'userInput': request.message, 'intent': result.get('intent','QA'), 'domain': result.get('domain','general'), 'needsWebSearch': result.get('needs_web_search', False), 'retrievedDocs': result.get('retrieved_docs', []), 'externalResults': result.get('external_results', []), 'answer': result.get('validated_output', ''), 'warnings': result.get('warnings', []), 'citations': result.get('citations', []), 'trace': result.get('trace', []), 'runMetadata': result.get('run_metadata', {})}
    execution_id = save_execution(execution_payload)
    return ChatResponse(executionId=execution_id, intent=result.get('intent','QA'), answer=result.get('validated_output', ''), warnings=result.get('warnings', []), citations=result.get('citations', []))