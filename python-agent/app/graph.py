from typing import Any, Dict
from langgraph.graph import StateGraph, END
from .agent_runtime import (
    route_intent_node,
    context_plan_node,
    retrieve_node,
    web_search_node,
    generate_node,
    validate_node
)

def build_graph():
    graph = StateGraph(dict)
    for name, node in [
        ('route_intent', route_intent_node),
        ('context_plan', context_plan_node),
        ('retrieve', retrieve_node),
        ('web_search', web_search_node),
        ('generate', generate_node),
        ('validate', validate_node)
    ]:
        graph.add_node(name, node)

    graph.set_entry_point('route_intent')
    graph.add_edge('route_intent', 'context_plan')
    graph.add_edge('context_plan', 'retrieve')
    graph.add_edge('retrieve', 'web_search')
    graph.add_edge('web_search', 'generate')
    graph.add_edge('generate', 'validate')
    graph.add_edge('validate', END)
    return graph.compile()

agent_graph = build_graph()