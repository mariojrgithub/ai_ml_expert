from typing import Any, Dict, Generator
from langchain_core.messages import HumanMessage
from .checker import check_citation_sufficiency, check_groundedness, check_relevance
from .citations import format_citations
from .llm import general_llm, code_llm
from .memory import read_session_memory, write_session_memory
from .prompt_registry import default_prompt_registry
from .rag import retrieve_context, context_to_text
from .router import classify_intent, plan_context
from .validators import validate_code, validate_mongo, validate_sql
from .web import external_context_to_text, run_web_search
from .tracing import timed_node
from .config import settings

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

def memory_read_node(state: Dict[str, Any]) -> Dict[str, Any]:
    turns, memory_context = read_session_memory(state['session_id'])
    return {'conversation_history': turns, 'memory_context': memory_context}

def retrieve_node(state: Dict[str, Any]) -> Dict[str, Any]:
    docs = retrieve_context(state['user_input']) if state.get('needs_rag', True) else []
    citations = [{'source': d.get('source', 'unknown'),'title': d.get('title', 'unknown'),'snippet': d.get('text', '')[:220],'similarity': d.get('similarity', 0.0),'rerank_score': d.get('rerank_score', 0.0)} for d in docs]
    return {'retrieved_docs': docs, 'citations': citations, 'retrieval_stats': {'doc_count': len(docs)}}

def web_search_node(state: Dict[str, Any]) -> Dict[str, Any]:
    results = run_web_search(state['user_input']) if state.get('needs_web_search', False) else []
    citations = list(state.get('citations', [])) + [{'source': r.get('source', 'unknown'),'title': r.get('title', 'unknown'),'snippet': r.get('snippet', ''),'url': r.get('url')} for r in results]
    return {'external_results': results, 'citations': citations, 'external_stats': {'result_count': len(results)}}

def generate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state['intent']; domain = state.get('domain'); question = state['user_input']
    context_docs = state.get('retrieved_docs', []); context = context_to_text(context_docs); external_context = external_context_to_text(state.get('external_results', []))
    prompt_name = 'qa'; model_name = 'general'
    if intent == 'QA':
        prompt_name = 'qa'; model_name = 'general'
        has_internal = bool(context_docs)
        has_external = bool(state.get('external_results'))
        if not (has_internal or has_external):
            return {'draft_output': 'I could not find sufficient context to answer this confidently.', 'prompt_name': prompt_name, 'prompt_version': PROMPTS.get(prompt_name).version, 'model_name': model_name, 'grounded': False}
        prompt = PROMPTS.render(prompt_name, {'question': question, 'context': context, 'external_context': external_context, 'conversation_history': state.get('memory_context', '')})
        text = general_llm().invoke([HumanMessage(content=prompt)]).content
        return {'draft_output': text, 'prompt_name': prompt_name, 'prompt_version': PROMPTS.get(prompt_name).version, 'model_name': model_name, 'grounded': has_internal or has_external}
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
    return {'draft_output': text, 'prompt_name': prompt_name, 'prompt_version': PROMPTS.get(prompt_name).version, 'model_name': model_name, 'grounded': bool(context_docs)}

def validate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state['intent']; text = state.get('draft_output') or ''; warnings = list(state.get('warnings', []))
    if intent == 'SQL': validated, new_warnings = validate_sql(text)
    elif intent == 'MONGO': validated, new_warnings = validate_mongo(text)
    elif intent == 'CODE': validated, new_warnings = validate_code(text, 'java' if state.get('domain') == 'java' else 'python')
    else: validated, new_warnings = text, []
    warnings.extend(new_warnings)
    if intent == 'QA' and not state.get('grounded', False): warnings.append('Grounded internal context not available for QA response.')
    if state.get('needs_web_search') and settings.web_search_enabled and not state.get('external_results'): warnings.append('Freshness was requested or inferred, but no MCP web-search result was returned.')
    if intent == 'QA' and state.get('grounded') and state.get('citations'):
        citation_suffix = format_citations(state['citations'])
        if citation_suffix:
            validated = validated + '\n\n' + citation_suffix
    return {'validated_output': validated, 'warnings': warnings}

def checker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run all three quality checks and collect findings into state."""
    intent = state['intent']
    draft = state.get('draft_output', '')
    warnings = list(state.get('warnings', []))

    # A — relevance
    rel_score, rel_passed = check_relevance(state['user_input'], draft)

    # B — groundedness (QA only)
    ground_score, ungrounded = check_groundedness(
        draft, state.get('retrieved_docs', []), state.get('external_results', []), intent
    )
    if intent == 'QA' and ground_score < settings.checker_groundedness_threshold:
        warnings.append(
            f'Groundedness score {ground_score:.2f} is below threshold '
            f'({settings.checker_groundedness_threshold}). Some claims may not be '
            'supported by retrieved context.'
        )

    # C — citation sufficiency
    cit_warnings = check_citation_sufficiency(intent, state.get('grounded', False), state.get('citations', []))
    warnings.extend(cit_warnings)

    return {
        'relevance_score': rel_score,
        'relevance_passed': rel_passed,
        'groundedness_score': ground_score,
        'ungrounded_sentences': ungrounded,
        'checker_findings': {
            'relevance_score': rel_score,
            'relevance_passed': rel_passed,
            'groundedness_score': ground_score,
            'ungrounded_sentence_count': len(ungrounded),
        },
        'warnings': warnings,
    }

def _memory_write(state: Dict[str, Any]) -> None:
    write_session_memory(
        session_id=state['session_id'],
        user_input=state['user_input'],
        final_answer=state.get('validated_output', ''),
        intent=state.get('intent', 'QA'),
        grounded=state.get('grounded', False),
        abstain=state.get('abstain', False),
    )

def run_agent_with_trace(session_id: str, user_input: str) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        'session_id': session_id, 'user_input': user_input,
        'warnings': [], 'trace': [], 'revision_count': 0, 'abstain': False,
    }

    # Pre-generation pipeline
    for name, fn in [
        ('route_intent', route_intent_node),
        ('context_plan', context_plan_node),
        ('memory_read', memory_read_node),
        ('retrieve', retrieve_node),
        ('web_search', web_search_node),
    ]:
        timed_node(name, fn, state)

    # Generate with relevance-check retry loop (Checker A gates revision)
    for attempt in range(settings.max_revision_attempts + 1):
        state['revision_count'] = attempt
        timed_node('generate', generate_node, state)
        rel_score, rel_passed = check_relevance(user_input, state.get('draft_output', ''))
        if rel_passed or attempt >= settings.max_revision_attempts:
            break

    # Post-generation pipeline
    for name, fn in [
        ('validate', validate_node),
        ('checker', checker_node),
    ]:
        timed_node(name, fn, state)

    # Abstain if relevance never passed and the response is ungrounded
    if not state.get('relevance_passed', True) and not state.get('grounded', False):
        state['abstain'] = True
        state['validated_output'] = (
            'I was unable to provide a sufficiently relevant answer for this question. '
            'Please try rephrasing or providing more context.'
        )

    _memory_write(state)

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
        'abstain': state.get('abstain', False),
        'relevance_score': state.get('relevance_score', 0.0),
        'groundedness_score': state.get('groundedness_score', 0.0),
        'revision_count': state.get('revision_count', 0),
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
        prompt = PROMPTS.render('qa', {
            'question': question,
            'context': context,
            'external_context': external_context,
            'conversation_history': state.get('memory_context', ''),
        })
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
    state: Dict[str, Any] = {
        'session_id': session_id, 'user_input': user_input,
        'warnings': [], 'trace': [], 'revision_count': 0, 'abstain': False,
    }

    for name, fn in [
        ('route_intent', route_intent_node),
        ('context_plan', context_plan_node),
        ('memory_read', memory_read_node),
        ('retrieve', retrieve_node),
        ('web_search', web_search_node),
    ]:
        timed_node(name, fn, state)

    # Early-exit for ungrounded QA — yield a single token then wrap up
    no_context = (
        state.get('intent') == 'QA'
        and not state.get('retrieved_docs')
        and not state.get('external_results')
    )
    if no_context:
        fallback = 'I could not find sufficient context to answer this confidently.'
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

    for name, fn in [('validate', validate_node), ('checker', checker_node)]:
        timed_node(name, fn, state)

    _memory_write(state)

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
        'abstain': state.get('abstain', False),
        'relevance_score': state.get('relevance_score', 0.0),
        'groundedness_score': state.get('groundedness_score', 0.0),
        'revision_count': state.get('revision_count', 0),
    }
    yield {'type': 'post', 'state': state}