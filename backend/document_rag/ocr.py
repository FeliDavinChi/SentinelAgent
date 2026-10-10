"""Replaceable OCR adapter. Tesseract is optional until OCR is needed."""

from typing import Any


def ocr_page(page_image: Any) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "OCR requires optional dependencies. Install pytesseract and Pillow, "
            "then install the Tesseract system binary."
        ) from exc

    if hasattr(page_image, "tobytes") and hasattr(page_image, "width"):
        image = Image.frombytes("RGB", (page_image.width, page_image.height), page_image.samples)
    else:
        image = page_image
    return pytesseract.image_to_string(image)