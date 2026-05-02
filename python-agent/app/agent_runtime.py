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


_QUERY_REWRITE_TEMPLATE = (
    "You are a search query optimizer. Given a conversation history and a follow-up "
    "question, rewrite the follow-up question as a concise, standalone search query "
    "that captures the user's intent without requiring prior context. "
    "Output ONLY the rewritten query — no explanation, no preamble.\n\n"
    "Conversation history:\n{history}\n\n"
    "Follow-up question: {question}\n\n"
    "Standalone search query:"
)

_MIN_HISTORY_TURNS_FOR_REWRITE = 1  # only rewrite when there is prior context


def query_rewrite_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Rewrite a conversational follow-up into a standalone retrieval query.

    Only triggers when conversation history exists; otherwise returns the
    original user_input unchanged to avoid unnecessary LLM calls.
    """
    history = state.get('memory_context', '').strip()
    if not history or len(state.get('conversation_history', [])) < _MIN_HISTORY_TURNS_FOR_REWRITE:
        return {'retrieval_query': state['user_input']}

    prompt = _QUERY_REWRITE_TEMPLATE.format(
        history=history[:1500],
        question=state['user_input'],
    )
    try:
        rewritten = general_llm().invoke([HumanMessage(content=prompt)]).content.strip()
        # Sanity check: if the model returns something suspiciously long or empty, fall back.
        if not rewritten or len(rewritten) > 500:
            rewritten = state['user_input']
    except Exception:
        rewritten = state['user_input']

    return {'retrieval_query': rewritten}

def retrieve_node(state: Dict[str, Any]) -> Dict[str, Any]:
    query = state.get('retrieval_query') or state['user_input']
    docs = retrieve_context(query) if state.get('needs_rag', True) else []
    citations = [{'source': d.get('source', 'unknown'),'title': d.get('title', 'unknown'),'snippet': d.get('text', '')[:220],'similarity': d.get('similarity', 0.0),'rerank_score': d.get('rerank_score', 0.0)} for d in docs]
    return {'retrieved_docs': docs, 'citations': citations, 'retrieval_stats': {'doc_count': len(docs)}}


def _should_run_web_search(state: Dict[str, Any]) -> bool:
    if not settings.web_search_enabled:
        return False

    # QA should always attempt web search when enabled so the model can still
    # answer from external context when internal retrieval is stale/irrelevant.
    if state.get('intent') == 'QA':
        return True

    if state.get('needs_web_search', False):
        return True

    # When the vector store has no usable context, fall back to the web for
    # knowledge-style and code-generation requests instead of failing fast.
    if state.get('retrieved_docs'):
        return False

    return state.get('intent') in {'CODE', 'SQL', 'MONGO'}

def web_search_node(state: Dict[str, Any]) -> Dict[str, Any]:
    should_search = _should_run_web_search(state)
    results = run_web_search(state['user_input']) if should_search else []
    citations = list(state.get('citations', [])) + [{'source': r.get('source', 'unknown'),'title': r.get('title', 'unknown'),'snippet': r.get('snippet', ''),'url': r.get('url')} for r in results]
    return {
        'external_results': results,
        'citations': citations,
        'external_stats': {'result_count': len(results)},
        'web_search_attempted': should_search,
    }

_REVISION_HINT = (
    "\n\n[Note: a previous attempt did not directly address the question. "
    "Please focus your answer specifically on: {question}]"
)


def _effective_question(state: Dict[str, Any]) -> str:
    """Return the question, optionally prefixed with a revision correction hint."""
    q = state['user_input']
    if state.get('_revision_failed'):
        return q + _REVISION_HINT.format(question=q)
    return q


def generate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state['intent']
    domain = state.get('domain')
    question = _effective_question(state)
    context_docs = state.get('retrieved_docs', [])
    context = context_to_text(context_docs)
    external_context = external_context_to_text(state.get('external_results', []))
    prompt_name = 'qa'
    model_name = 'general'

    if intent == 'QA':
        has_internal = bool(context_docs)
        has_external = bool(state.get('external_results'))
        if not (has_internal or has_external):
            return {
                'draft_output': 'I could not find sufficient context to answer this confidently.',
                'prompt_name': prompt_name,
                'prompt_version': PROMPTS.get(prompt_name).version,
                'model_name': model_name,
                'grounded': False,
            }
        prompt = PROMPTS.render(prompt_name, {
            'question': question,
            'context': context,
            'external_context': external_context,
            'conversation_history': state.get('memory_context', ''),
        })
        text = general_llm().invoke([HumanMessage(content=prompt)]).content
        return {
            'draft_output': text,
            'prompt_name': prompt_name,
            'prompt_version': PROMPTS.get(prompt_name).version,
            'model_name': model_name,
            'grounded': has_internal or has_external,
        }

    elif intent == 'SQL':
        prompt_name = 'sql'
        prompt = PROMPTS.render(prompt_name, {'question': question, 'context': context})
        text = general_llm().invoke([HumanMessage(content=prompt)]).content

    elif intent == 'MONGO':
        prompt_name = 'mongo'
        prompt = PROMPTS.render(prompt_name, {'question': question, 'context': context})
        text = general_llm().invoke([HumanMessage(content=prompt)]).content

    elif intent == 'CODE' and domain == 'java':
        prompt_name = 'code_java'
        model_name = 'code'
        prompt = PROMPTS.render(prompt_name, {
            'question': question, 'context': context, 'external_context': external_context,
        })
        text = code_llm().invoke([HumanMessage(content=prompt)]).content

    else:
        prompt_name = _CODE_PROMPT_MAP.get(domain or '', 'code_python')
        model_name = 'code'
        prompt = PROMPTS.render(prompt_name, {
            'question': question, 'context': context, 'external_context': external_context,
        })
        text = code_llm().invoke([HumanMessage(content=prompt)]).content

    return {
        'draft_output': text,
        'prompt_name': prompt_name,
        'prompt_version': PROMPTS.get(prompt_name).version,
        'model_name': model_name,
        'grounded': bool(context_docs),
    }

def validate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Syntax and safety validation only — does NOT append citations."""
    intent = state['intent']
    text = state.get('draft_output') or ''
    warnings = list(state.get('warnings', []))

    if intent == 'SQL':
        validated, new_warnings = validate_sql(text)
    elif intent == 'MONGO':
        validated, new_warnings = validate_mongo(text)
    elif intent == 'CODE':
        lang = 'java' if state.get('domain') == 'java' else 'python'
        validated, new_warnings = validate_code(text, lang)
    else:
        validated, new_warnings = text, []

    warnings.extend(new_warnings)

    if intent == 'QA' and not state.get('grounded', False):
        warnings.append('Grounded internal context not available for QA response.')
    if state.get('needs_web_search') and settings.web_search_enabled and not state.get('external_results'):
        warnings.append('Freshness was requested or inferred, but no MCP web-search result was returned.')
    if state.get('web_search_attempted') and not state.get('external_results'):
        warnings.append('Web search was attempted, but returned no external results (or web search provider is not configured).')

    return {'validated_output': validated, 'warnings': warnings}


def format_output_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Append formatted citations to the validated output for grounded QA.

    Separated from validate_node so that citation formatting runs AFTER the
    checker has seen the clean draft \u2014 the checker always reads draft_output,
    not validated_output.
    """
    intent = state['intent']
    validated = state.get('validated_output', '')

    if intent == 'QA' and state.get('grounded') and state.get('citations'):
        citation_suffix = format_citations(state['citations'])
        if citation_suffix:
            validated = validated + '\n\n' + citation_suffix

    return {'validated_output': validated}

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


def abstain_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Set abstain=True and overwrite output when quality is unrecoverable.

    Triggers when relevance never passed AND the answer is ungrounded.
    Returns an empty dict (no-op) when quality checks passed.
    """
    if not state.get('relevance_passed', True) and not state.get('grounded', False):
        fallback = (
            'I was unable to provide a sufficiently relevant answer for this question. '
            'Please try rephrasing or providing more context.'
        )
        return {'abstain': True, 'validated_output': fallback}
    return {}


def memory_write_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Persist the current turn to session memory (side-effect node).

    Always returns an empty dict — memory write is a side-effect, not a
    state mutation.  timed_node records the latency for observability.
    """
    _memory_write(state)
    return {}


def finalize_node(state: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    """Assemble final_answer and run_metadata as the last pipeline step."""
    final_answer = state.get('validated_output', '')
    return {
        'final_answer': final_answer,
        'run_metadata': {
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
        },
    }

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
        ('query_rewrite', query_rewrite_node),
        ('retrieve', retrieve_node),
        ('web_search', web_search_node),
    ]:
        timed_node(name, fn, state)

    # Generate with retry loop gated by relevance.
    # check_relevance runs once in checker_node — we do NOT duplicate it here.
    # On each retry we inject a hint into state so generate_node can tighten
    # the prompt (see _REVISION_HINT below).
    for attempt in range(settings.max_revision_attempts + 1):
        state['revision_count'] = attempt
        timed_node('generate', generate_node, state)
        # Peek at relevance to decide whether to retry, without duplicating
        # the scorer result that checker_node will produce authoritatively.
        _draft = state.get('draft_output', '')
        _rel_score, _rel_passed = check_relevance(user_input, _draft)
        if _rel_passed or attempt >= settings.max_revision_attempts:
            break
        # Flag poor relevance so generate_node can add a correction hint.
        state['_revision_failed'] = True

    # Post-generation pipeline
    for name, fn in [
        ('validate', validate_node),
        ('format_output', format_output_node),
        ('checker', checker_node),
        ('abstain', abstain_node),
    ]:
        timed_node(name, fn, state)

    # Canonical output field — single source of truth for callers.
    # (set by abstain_node if triggered, or kept from validate_node)
    state['final_answer'] = state.get('validated_output', '')

    timed_node('memory_write', memory_write_node, state)
    timed_node('finalize', lambda s: finalize_node(s, session_id), state)
    return state


def _build_prompt_for_state(state: Dict[str, Any]) -> tuple[Any, str]:
    """Return (llm, prompt_text) for streaming, without invoking the LLM.

    Uses _effective_question so revision hints are applied consistently
    across both streaming and non-streaming paths.
    """
    intent = state['intent']
    domain = state.get('domain')
    question = _effective_question(state)
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
        ('query_rewrite', query_rewrite_node),
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

    for name, fn in [
        ('validate', validate_node),
        ('format_output', format_output_node),
        ('checker', checker_node),
        ('abstain', abstain_node),
    ]:
        timed_node(name, fn, state)

    state['final_answer'] = state.get('validated_output', '')
    timed_node('memory_write', memory_write_node, state)
    timed_node('finalize', lambda s: finalize_node(s, session_id), state)
    yield {'type': 'post', 'state': state}