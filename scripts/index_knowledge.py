"""Index the local synthetic knowledge base."""

from app.rag.retriever import KnowledgeRetriever


if __name__ == "__main__":
    retriever = KnowledgeRetriever()
    print(f"Indexed {retriever.index_documents(force=True)} knowledge chunks")
