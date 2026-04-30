"""
AgentState — the canonical state shape passed between every graph node.

Fields are annotated with storage intent:
    EPHEMERAL  — never persisted; discarded after the request
    PERSISTED  — written to MongoDB executions collection
    LOGGED     — included in eval/observability payloads
"""
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    # --- Identity ----------------------------------------------------------
    session_id: str                        # PERSISTED
    user_id: Optional[str]                 # PERSISTED (future)

    # --- Input -------------------------------------------------------------
    user_input: str                        # PERSISTED
    normalized_input: str                  # EPHEMERAL

    # --- Routing -----------------------------------------------------------
    intent: str                            # PERSISTED
    domain: Optional[str]                  # PERSISTED
    confidence: float                      # LOGGED
    ambiguity_flag: bool                   # EPHEMERAL

    # --- Retrieval flags ---------------------------------------------------
    needs_rag: bool                        # EPHEMERAL
    needs_web_search: bool                 # EPHEMERAL

    # --- Memory (populated by memory_read_node) ----------------------------
    conversation_history: List[Dict]       # EPHEMERAL  (session-scoped turns)
    memory_context: str                    # EPHEMERAL  (rendered for prompt)

    # --- Retrieved context -------------------------------------------------
    retrieved_docs: List[Dict]             # LOGGED (IDs only in persistence)
    retrieval_stats: Dict                  # PERSISTED
    external_results: List[Dict]           # LOGGED (URLs only)
    external_stats: Dict                   # PERSISTED

    # --- Generation --------------------------------------------------------
    draft_output: str                      # EPHEMERAL (debug/eval only)
    prompt_name: str                       # PERSISTED
    prompt_version: str                    # PERSISTED
    model_name: str                        # PERSISTED

    # --- Checker findings --------------------------------------------------
    relevance_score: float                 # PERSISTED
    relevance_passed: bool                 # PERSISTED
    groundedness_score: float              # PERSISTED
    ungrounded_sentences: List[str]        # LOGGED
    checker_findings: Dict[str, Any]       # PERSISTED

    # --- Output ------------------------------------------------------------
    validated_output: str                  # EPHEMERAL (intermediate)
    citations: List[Dict]                  # PERSISTED
    final_answer: str                      # PERSISTED
    grounded: bool                         # PERSISTED

    # --- Control flow ------------------------------------------------------
    revision_count: int                    # EPHEMERAL
    abstain: bool                          # PERSISTED

    # --- Warnings ----------------------------------------------------------
    warnings: List[str]                    # PERSISTED

    # --- Metadata ----------------------------------------------------------
    trace: List[Dict]                      # PERSISTED
    run_metadata: Dict                     # PERSISTED
