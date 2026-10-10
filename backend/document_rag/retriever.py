"""Stable retrieval contract for the future Gemini agent."""

from typing import Any, Mapping

from .embeddings import EmbeddingModel, TfidfEmbeddingModel
from .schemas import Evidence
from .vector_store import InMemoryVectorStore, VectorStore


class SearchService:
    def __init__(self, store: VectorStore, embedding_model: EmbeddingModel) -> None:
        self.store = store
        self.embedding_model = embedding_model

    def search_documents(
        self,
        query: str,
        authorized_document_ids: list[str] | set[str] | None = None,
        top_k: int = 5,
    ) -> dict[str, list[dict[str, Any]]]:
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be greater than zero")
        query_vector = self.embedding_model.embed_text(query)
        matches = self.store.search(query_vector, top_k, None if authorized_document_ids is None else set(authorized_document_ids))
        return {"results": [Evidence(
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            title=chunk.title,
            page_number=chunk.page_number,
            content=chunk.text,
            department=chunk.department,
            classification=chunk.classification,
            owner=chunk.owner,
            version=chunk.version,
            effective_date=chunk.effective_date,
            score=round(score, 6),
            metadata=chunk.metadata,
        ).to_dict() for chunk, score in matches]}


_default_embedding_model = TfidfEmbeddingModel()
_default_store = InMemoryVectorStore(_default_embedding_model)
_default_service = SearchService(_default_store, _default_embedding_model)


def search_documents(
    query: str,
    authorized_document_ids: list[str] | set[str] | None = None,
    top_k: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """Search the configured local store; production should inject an RLS-scoped store."""
    return _default_service.search_documents(query, authorized_document_ids, top_k)


def default_search_service() -> SearchService:
    return _default_service