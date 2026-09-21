"""Allowlisted knowledge-base tool."""

from typing import Any

from app.rag.retriever import KnowledgeRetriever


def search_knowledge_base(query: Any, retriever: KnowledgeRetriever) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    results = retriever.search(query.strip())
    return {
        "query": query.strip(),
        "results": [{"text": item.text, "source": item.source} for item in results],
    }
