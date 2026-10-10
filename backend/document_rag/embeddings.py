"""Provider-neutral embedding interface and a deterministic local implementation."""

from collections import Counter
import math
import re
from typing import Protocol, Sequence


class EmbeddingModel(Protocol):
    def embed_text(self, text: str) -> list[float]: ...
    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...


class TfidfEmbeddingModel:
    """Small offline embedding model for development; replace in production."""

    def __init__(self) -> None:
        self._vocabulary: dict[str, int] = {}
        self._idf: list[float] = []

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def fit(self, texts: Sequence[str]) -> None:
        document_frequency: Counter[str] = Counter()
        for text in texts:
            document_frequency.update(set(self._tokens(text)))
        terms = sorted(document_frequency)
        self._vocabulary = {term: index for index, term in enumerate(terms)}
        count = max(len(texts), 1)
        self._idf = [math.log((1 + count) / (1 + document_frequency[term])) + 1 for term in terms]

    def embed_text(self, text: str) -> list[float]:
        if not self._vocabulary:
            self.fit([text])
        counts = Counter(self._tokens(text))
        vector = [0.0] * len(self._vocabulary)
        for term, frequency in counts.items():
            index = self._vocabulary.get(term)
            if index is not None:
                vector[index] = (1 + math.log(frequency)) * self._idf[index]
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if texts:
            self.fit(texts)
        return [self.embed_text(text) for text in texts]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))