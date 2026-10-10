"""Configurable word-based chunking that retains page and document metadata."""

from .schemas import DocumentMetadata, PageText, TextChunk


def chunk_pages(
    pages: list[PageText],
    metadata: DocumentMetadata,
    *,
    chunk_size: int = 180,
    overlap: int = 30,
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    chunks: list[TextChunk] = []
    for page in pages:
        words = page.text.split()
        if not words:
            continue
        step = chunk_size - overlap
        for start in range(0, len(words), step):
            text = " ".join(words[start:start + chunk_size]).strip()
            if not text:
                continue
            chunk_number = len([chunk for chunk in chunks if chunk.page_number == page.page_number]) + 1
            chunks.append(TextChunk(
                chunk_id=f"{metadata.document_id}-P{page.page_number}-C{chunk_number}",
                document_id=metadata.document_id,
                page_number=page.page_number,
                title=metadata.title,
                department=metadata.department,
                classification=metadata.classification,
                owner=metadata.owner,
                version=metadata.version,
                effective_date=metadata.effective_date,
                text=text,
                metadata={
                    "allowed_departments": metadata.allowed_departments,
                    "allowed_roles": metadata.allowed_roles,
                    "used_ocr": page.used_ocr,
                    **metadata.extra,
                },
            ))
            if start + chunk_size >= len(words):
                break
    return chunks