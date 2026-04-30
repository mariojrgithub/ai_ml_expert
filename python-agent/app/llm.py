from langchain_ollama import ChatOllama, OllamaEmbeddings
from .config import settings

# Module-level singletons — one instance per model config, shared across requests.
_general_llm: ChatOllama | None = None
_code_llm: ChatOllama | None = None
_embedding_model: OllamaEmbeddings | None = None


def general_llm() -> ChatOllama:
    global _general_llm
    if _general_llm is None:
        _general_llm = ChatOllama(
            model=settings.general_model,
            base_url=settings.ollama_base_url,
            temperature=0.1,
        )
    return _general_llm


def code_llm() -> ChatOllama:
    global _code_llm
    if _code_llm is None:
        _code_llm = ChatOllama(
            model=settings.code_model,
            base_url=settings.ollama_base_url,
            temperature=0.1,
        )
    return _code_llm


def embedding_model() -> OllamaEmbeddings:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = OllamaEmbeddings(
            model=settings.embedding_model,
            base_url=settings.ollama_base_url,
        )
    return _embedding_model