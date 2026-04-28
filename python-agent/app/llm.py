from langchain_ollama import ChatOllama, OllamaEmbeddings
from .config import settings

def general_llm() -> ChatOllama:
    return ChatOllama(
        model=settings.general_model,
        base_url=settings.ollama_base_url,
        temperature=0.1
    )

def code_llm() -> ChatOllama:
    return ChatOllama(
        model=settings.code_model,
        base_url=settings.ollama_base_url,
        temperature=0.1
    )

def embedding_model() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=settings.embedding_model,
        base_url=settings.ollama_base_url
    )