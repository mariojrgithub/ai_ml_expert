from typing import Any, Dict, Generator
from langchain_core.messages import HumanMessage
from .llm import general_llm, code_llm
from .prompt_registry import default_prompt_registry
from .rag import retrieve_context, context_to_text
from .router import classify_intent, plan_context
from .validators import validate_code, validate_mongo, validate_sql
from .web import external_context_to_text, run_web_search
from .tracing import timed_node

PROMPTS = default_prompt_registry()

# Maps CODE-intent domain → prompt name.
# Domains not listed here fall back to the general code_python prompt.
_CODE_PROMPT_MAP: Dict[str, str] = {
    "java":          "code_java",
    "deep_learning": "code_deep_learning",
    "data_science":  "code_data_science",
    "algorithms":    "code_algorithms",
    "security":      "code_security",
    "finance":       "code_finance",
}

def route_intent_node(state: Dict[str, Any]) -> Dict[str, Any]: return classify_intent(state['user_input'])
def context_plan_node(state: Dict[str, Any]) -> Dict[str, Any]: return plan_context(state['user_input'], state['intent'])
def retrieve_node(state: Dict[str, Any]) -> Dict[str, Any]:
    docs = retrieve_context(state['user_input']) if state.get('needs_rag', True) else []
    citations = [{'source': d.get('source', 'unknown'),'title': d.get('title', 'unknown'),'snippet': d.get('text', '')[:220],'similarity': d.get('similarity', 0.0),'rerank_score': d.get('rerank_score', 0.0)} for d in docs]
    return {'retrieved_docs': docs, 'citations': citations, 'retrieval_stats': {'doc_count': len(docs)}}
def web_search_node(state: Dict[str, Any]) -> Dict[str, Any]:
    results = run_web_search(state['user_input']) if state.get('needs_web_search', False) else []
    citations = list(state.get('citations', [])) + [{'source': r.get('source', 'unknown'),'title': r.get('title', 'unknown'),'snippet': r.get('snippet', '')} for r in results]
    return {'external_results': results, 'citations': citations, 'external_stats': {'result_count': len(results)}}
def generate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state['intent']; domain = state.get('domain'); question = state['user_input']
    context_docs = state.get('retrieved_docs', []); context = context_to_text(context_docs); external_context = external_context_to_text(state.get('external_results', []))
    prompt_name = 'qa'; model_name = 'general'
    if intent == 'QA':
        prompt_name = 'qa'; model_name = 'general'
        if not context_docs:
            return {'draft_output': 'I could not find sufficient internal context to answer this confidently.', 'prompt_name': prompt_name, 'prompt_version': PROMPTS.get(prompt_name).version, 'model_name': model_name, 'grounded': False}
        prompt = PROMPTS.render(prompt_name, {'question': question,'context': context,'external_context': external_context})
        text = general_llm().invoke([HumanMessage(content=prompt)]).content
        return {'draft_output': text, 'prompt_name': prompt_name, 'prompt_version': PROMPTS.get(prompt_name).version, 'model_name': model_name, 'grounded': True}
    elif intent == 'SQL':
        prompt_name = 'sql'; model_name = 'general'
        prompt = PROMPTS.render(prompt_name, {'question': question,'context': context})
        text = general_llm().invoke([HumanMessage(content=prompt)]).content
    elif intent == 'MONGO':
        prompt_name = 'mongo'; model_name = 'general'
        prompt = PROMPTS.render(prompt_name, {'question': question,'context': context})
        text = general_llm().invoke([HumanMessage(content=prompt)]).content
    elif intent == 'CODE' and domain == 'java':
        prompt_name = 'code_java'; model_name = 'code'
        prompt = PROMPTS.render(prompt_name, {'question': question,'context': context,'external_context': external_context})
        text = code_llm().invoke([HumanMessage(content=prompt)]).content
    else:
        prompt_name = _CODE_PROMPT_MAP.get(domain or '', 'code_python'); model_name = 'code'
        prompt = PROMPTS.render(prompt_name, {'question': question,'context': context,'external_context': external_context})
        text = code_llm().invoke([HumanMessage(content=prompt)]).content
    return {'draft_output': text, 'prompt_name': prompt_name, 'prompt_version': PROMPTS.get(prompt_name).version, 'model_name': model_name, 'grounded': bool(context_docs) if intent == 'QA' else True}
def validate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state['intent']; text = state.get('draft_output') or ''; warnings = list(state.get('warnings', []))
    if intent == 'SQL': validated, new_warnings = validate_sql(text)
    elif intent == 'MONGO': validated, new_warnings = validate_mongo(text)
    elif intent == 'CODE': validated, new_warnings = validate_code(text, 'java' if state.get('domain') == 'java' else 'python')
    else: validated, new_warnings = text, []
    warnings.extend(new_warnings)
    if intent == 'QA' and not state.get('grounded', False): warnings.append('Grounded internal context not available for QA response.')
    if state.get('needs_web_search') and not state.get('external_results'): warnings.append('Freshness was requested or inferred, but no MCP web-search result was returned.')
    return {'validated_output': validated, 'warnings': warnings}

def run_agent_with_trace(session_id: str, user_input: str) -> Dict[str, Any]:
    state: Dict[str, Any] = {'session_id': session_id, 'user_input': user_input, 'warnings': [], 'trace': []}
    for name, fn in [('route_intent', route_intent_node), ('context_plan', context_plan_node), ('retrieve', retrieve_node), ('web_search', web_search_node), ('generate', generate_node), ('validate', validate_node)]:
        timed_node(name, fn, state)
    state['run_metadata'] = {
        'session_id': session_id,
        'intent': state.get('intent'),
        'domain': state.get('domain'),
        'prompt_name': state.get('prompt_name'),
        'prompt_version': state.get('prompt_version'),
        'model_name': state.get('model_name'),
        'retrieved_doc_count': state.get('retrieval_stats', {}).get('doc_count', 0),
        'external_result_count': state.get('external_stats', {}).get('result_count', 0),
        'grounded': state.get('grounded', False),
    }
    return state


def _build_prompt_for_state(state: Dict[str, Any]) -> tuple[Any, str]:
    """Return (llm, prompt_text) for streaming, without invoking the LLM."""
    intent = state['intent']
    domain = state.get('domain')
    question = state['user_input']
    context = context_to_text(state.get('retrieved_docs', []))
    external_context = external_context_to_text(state.get('external_results', []))

    if intent == 'QA':
        prompt = PROMPTS.render('qa', {'question': question, 'context': context, 'external_context': external_context})
        return general_llm(), prompt
    elif intent == 'SQL':
        prompt = PROMPTS.render('sql', {'question': question, 'context': context})
        return general_llm(), prompt
    elif intent == 'MONGO':
        prompt = PROMPTS.render('mongo', {'question': question, 'context': context})
        return general_llm(), prompt
    elif intent == 'CODE' and domain == 'java':
        prompt = PROMPTS.render('code_java', {'question': question, 'context': context, 'external_context': external_context})
        return code_llm(), prompt
    else:
        prompt_name = _CODE_PROMPT_MAP.get(domain or '', 'code_python')
        prompt = PROMPTS.render(prompt_name, {'question': question, 'context': context, 'external_context': external_context})
        return code_llm(), prompt


def stream_agent_tokens(session_id: str, user_input: str) -> Generator[Dict[str, Any], None, None]:
    """
    Runs the pipeline up to (but not including) the LLM call, then streams
    tokens from the LLM as they arrive.  Yields dicts:
      {'type': 'pre',   'state': state}        — after routing/retrieval, before generation
      {'type': 'token', 'content': str}         — one LLM token
      {'type': 'post',  'state': state}         — after validation with full state
    """
    state: Dict[str, Any] = {'session_id': session_id, 'user_input': user_input, 'warnings': [], 'trace': []}

    for name, fn in [
        ('route_intent', route_intent_node),
        ('context_plan', context_plan_node),
        ('retrieve', retrieve_node),
        ('web_search', web_search_node),
    ]:
        timed_node(name, fn, state)

    # Early-exit for ungrounded QA — yield a single token then wrap up
    no_context = (state.get('intent') == 'QA' and not state.get('retrieved_docs'))
    if no_context:
        fallback = 'I could not find sufficient internal context to answer this confidently.'
        state.update({'draft_output': fallback, 'grounded': False, 'prompt_name': 'qa', 'model_name': 'general'})
        yield {'type': 'pre', 'state': state}
        yield {'type': 'token', 'content': fallback}
    else:
        yield {'type': 'pre', 'state': state}
        llm, prompt = _build_prompt_for_state(state)
        full_tokens = []
        for chunk in llm.stream([HumanMessage(content=prompt)]):
            token = chunk.content if hasattr(chunk, 'content') else str(chunk)
            full_tokens.append(token)
            yield {'type': 'token', 'content': token}
        state['draft_output'] = ''.join(full_tokens)

    timed_node('validate', validate_node, state)
    state['run_metadata'] = {
        'session_id': session_id,
        'intent': state.get('intent'),
        'domain': state.get('domain'),
        'prompt_name': state.get('prompt_name'),
        'prompt_version': state.get('prompt_version'),
        'model_name': state.get('model_name'),
        'retrieved_doc_count': state.get('retrieval_stats', {}).get('doc_count', 0),
        'external_result_count': state.get('external_stats', {}).get('result_count', 0),
        'grounded': state.get('grounded', False),
    }
    yield {'type': 'post', 'state': state}