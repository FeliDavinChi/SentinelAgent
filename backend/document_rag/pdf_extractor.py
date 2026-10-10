"""PDF text extraction with page preservation and OCR fallback."""

from pathlib import Path
from typing import Callable

import pymupdf as fitz

from .normalization import normalize_text
from .ocr import ocr_page
from .schemas import DocumentProcessingError, DocumentMetadata, PageText


def has_meaningful_text(text: str, minimum_characters: int = 10) -> bool:
    return len(" ".join(text.split())) >= minimum_characters


def extract_pdf_pages(
    file_path: str | Path,
    metadata: DocumentMetadata,
    *,
    ocr_function: Callable[[object], str] = ocr_page,
    ocr_dpi: int = 150,
    minimum_text_characters: int = 10,
) -> list[PageText]:
    path = Path(file_path)
    if not path.is_file():
        raise DocumentProcessingError(f"PDF file does not exist: {path}")
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise DocumentProcessingError(f"Unable to open PDF '{path}': {exc}") from exc

    pages: list[PageText] = []
    try:
        for index, page in enumerate(document):
            extracted = normalize_text(page.get_text("text"))
            used_ocr = False
            if not has_meaningful_text(extracted, minimum_text_characters):
                try:
                    image = page.get_pixmap(dpi=ocr_dpi, alpha=False)
                    extracted = normalize_text(ocr_function(image))
                    used_ocr = True
                except Exception as exc:
                    raise DocumentProcessingError(
                        f"OCR failed on page {index + 1} of '{path}': {exc}"
                    ) from exc
            pages.append(PageText(metadata.document_id, index + 1, extracted, used_ocr))
    finally:
        document.close()
    return pages