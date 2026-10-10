"""Vector storage contract and an in-memory development implementation."""

from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence

from .embeddings import EmbeddingModel, TfidfEmbeddingModel, cosine_similarity
from .schemas import TextChunk


class VectorStore(Protocol):
    def add(self, chunks: Iterable[TextChunk]) -> int: ...
    def search(self, query_vector: Sequence[float], top_k: int = 5, authorized_document_ids: set[str] | None = None) -> list[tuple[TextChunk, float]]: ...


@dataclass
class _StoredChunk:
    chunk: TextChunk
    vector: list[float]


class InMemoryVectorStore:
    """Development-only store. It is not an authorization boundary."""

    def __init__(self, embedding_model: EmbeddingModel | None = None) -> None:
        self.embedding_model = embedding_model or TfidfEmbeddingModel()
        self._items: dict[str, _StoredChunk] = {}

    def add(self, chunks: Iterable[TextChunk]) -> int:
        chunk_list = list(chunks)
        if not chunk_list:
            return 0
        if any(chunk.chunk_id in self._items for chunk in chunk_list):
            duplicate = next(chunk.chunk_id for chunk in chunk_list if chunk.chunk_id in self._items)
            raise ValueError(f"Duplicate chunk ID: {duplicate}")
        all_chunks = [item.chunk for item in self._items.values()] + chunk_list
        vectors = self.embedding_model.embed_texts([chunk.text for chunk in all_chunks])
        self._items = {}
        for chunk, vector in zip(all_chunks, vectors):
            if chunk.chunk_id in self._items:
                raise ValueError(f"Duplicate chunk ID: {chunk.chunk_id}")
            self._items[chunk.chunk_id] = _StoredChunk(chunk, vector)
        return len(chunk_list)

    def search(self, query_vector: Sequence[float], top_k: int = 5, authorized_document_ids: set[str] | None = None) -> list[tuple[TextChunk, float]]:
        candidates = self._items.values()
        if authorized_document_ids is not None:
            candidates = (item for item in candidates if item.chunk.document_id in authorized_document_ids)
        ranked = [(item.chunk, cosine_similarity(query_vector, item.vector)) for item in candidates]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:max(top_k, 0)]

    def count(self) -> int:
        return len(self._items)