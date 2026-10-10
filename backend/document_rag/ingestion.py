"""Public ingestion pipeline."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .chunker import chunk_pages
from .embeddings import EmbeddingModel, TfidfEmbeddingModel
from .pdf_extractor import extract_pdf_pages
from .schemas import DocumentMetadata, TextChunk
from .vector_store import InMemoryVectorStore, VectorStore


@dataclass(frozen=True)
class IngestionResult:
    document_id: str
    page_count: int
    chunk_count: int
    ocr_pages: list[int]
    chunks: list[TextChunk]


def ingest_document(
    file_path: str | Path,
    metadata: Mapping[str, Any] | DocumentMetadata,
    *,
    store: VectorStore | None = None,
    embedding_model: EmbeddingModel | None = None,
    chunk_size: int = 180,
    overlap: int = 30,
) -> IngestionResult:
    document_metadata = metadata if isinstance(metadata, DocumentMetadata) else DocumentMetadata.from_mapping(metadata)
    if store is None and embedding_model is None:
        from .retriever import default_search_service
        default_service = default_search_service()
        target_store = default_service.store
    else:
        target_store = store or InMemoryVectorStore(embedding_model or TfidfEmbeddingModel())
    pages = extract_pdf_pages(file_path, document_metadata)
    chunks = chunk_pages(pages, document_metadata, chunk_size=chunk_size, overlap=overlap)
    target_store.add(chunks)
    return IngestionResult(
        document_id=document_metadata.document_id,
        page_count=len(pages),
        chunk_count=len(chunks),
        ocr_pages=[page.page_number for page in pages if page.used_ocr],
        chunks=chunks,
    )