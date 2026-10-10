"""Document ingestion, OCR, chunking, embeddings, and retrieval."""

from .embeddings import EmbeddingModel, TfidfEmbeddingModel
from .ingestion import IngestionResult, ingest_document
from .retriever import SearchService, search_documents
from .schemas import DocumentMetadata, Evidence, TextChunk
from .vector_store import InMemoryVectorStore, VectorStore

__all__ = [
    "DocumentMetadata",
    "EmbeddingModel",
    "Evidence",
    "InMemoryVectorStore",
    "IngestionResult",
    "SearchService",
    "TextChunk",
    "TfidfEmbeddingModel",
    "VectorStore",
    "ingest_document",
    "search_documents",
]