"""Source-faithful text cleanup."""

import re


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<!\n)-\n(?=\w)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()