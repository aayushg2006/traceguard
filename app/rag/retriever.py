"""Local ChromaDB RAG index backed by Ollama embeddings."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import chromadb
from chromadb.config import Settings

from app.config import ROOT, app_config, model_config
from app.ollama_client import OllamaClient


PUBLIC_DOCUMENTS = {
    "refund_policy.md",
    "shipping_policy.md",
    "support_policy.md",
    "product_faq.md",
}


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    source: str
    distance: float | None = None


def _chunks(text: str, size: int, overlap: int) -> Iterable[str]:
    words = text.split()
    step = max(1, size - overlap)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + size]).strip()
        if chunk:
            yield chunk
        if start + size >= len(words):
            break


class KnowledgeRetriever:
    def __init__(
        self,
        client: OllamaClient | None = None,
        config: dict[str, Any] | None = None,
        chroma_client: Any | None = None,
    ) -> None:
        settings = config or app_config()
        rag = settings.get("rag", {})
        self.documents_path = ROOT / str(rag.get("documents_path", "app/rag/documents"))
        self.persist_directory = ROOT / str(rag.get("persist_directory", "data/chroma"))
        self.collection_name = str(rag.get("collection_name", "enterprise_support"))
        self.top_k = int(rag.get("top_k", 3))
        self.chunk_size = int(rag.get("chunk_size", 700))
        self.chunk_overlap = int(rag.get("chunk_overlap", 100))
        self.ollama = client or OllamaClient(model_config())
        self.chroma = chroma_client or chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.chroma.get_or_create_collection(self.collection_name)

    def index_documents(self, force: bool = False) -> int:
        files = sorted(self.documents_path.glob("*.md"))
        if not files:
            raise RuntimeError(f"No knowledge documents found in {self.documents_path}")
        if force:
            try:
                self.chroma.delete_collection(self.collection_name)
            except Exception:
                pass
            self.collection = self.chroma.get_or_create_collection(self.collection_name)
        elif self.collection.count() > 0:
            return self.collection.count()

        texts: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, str]] = []
        for path in files:
            content = path.read_text(encoding="utf-8")
            for index, chunk in enumerate(_chunks(content, self.chunk_size, self.chunk_overlap)):
                texts.append(chunk)
                ids.append(f"{path.stem}-{index}")
                metadatas.append({"source": path.name})
        embeddings = self.ollama.embed(texts)
        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(texts)

    def search(self, query: str, top_k: int | None = None, include_internal: bool = False) -> list[RetrievedChunk]:
        if not query.strip():
            return []
        if self.collection.count() == 0:
            self.index_documents()
        embedding = self.ollama.embed([query])[0]
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k or self.top_k,
            include=["documents", "metadatas", "distances"],
        )
        chunks: list[RetrievedChunk] = []
        for text, metadata, distance in zip(
            result.get("documents", [[]])[0],
            result.get("metadatas", [[]])[0],
            result.get("distances", [[]])[0],
        ):
            source = str((metadata or {}).get("source", "unknown"))
            if not include_internal and source not in PUBLIC_DOCUMENTS:
                continue
            chunks.append(RetrievedChunk(str(text), source, float(distance)))
        return chunks
