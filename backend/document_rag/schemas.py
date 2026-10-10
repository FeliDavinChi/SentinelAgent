"""Stable data contracts for the document RAG module."""

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


REQUIRED_METADATA = ("document_id", "title", "department", "classification", "owner")


class DocumentRAGError(Exception):
    """Base error for recoverable document RAG failures."""


class MetadataError(DocumentRAGError, ValueError):
    """Raised when required document metadata is absent or invalid."""


class DocumentProcessingError(DocumentRAGError):
    """Raised when a document cannot be processed."""


@dataclass(frozen=True)
class DocumentMetadata:
    document_id: str
    title: str
    department: str
    classification: str
    owner: str
    allowed_departments: list[str] = field(default_factory=list)
    allowed_roles: list[str] = field(default_factory=list)
    version: str | None = None
    effective_date: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, metadata: Mapping[str, Any]) -> "DocumentMetadata":
        missing = [key for key in REQUIRED_METADATA if not metadata.get(key)]
        if missing:
            raise MetadataError(f"Missing required metadata: {', '.join(missing)}")
        known = {
            "document_id", "title", "department", "classification", "owner",
            "allowed_departments", "allowed_roles", "version", "effective_date",
        }
        return cls(
            document_id=str(metadata["document_id"]),
            title=str(metadata["title"]),
            department=str(metadata["department"]),
            classification=str(metadata["classification"]),
            owner=str(metadata["owner"]),
            allowed_departments=list(metadata.get("allowed_departments") or []),
            allowed_roles=list(metadata.get("allowed_roles") or []),
            version=None if metadata.get("version") is None else str(metadata["version"]),
            effective_date=None if metadata.get("effective_date") is None else str(metadata["effective_date"]),
            extra={key: value for key, value in metadata.items() if key not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PageText:
    document_id: str
    page_number: int
    text: str
    used_ocr: bool = False


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    document_id: str
    page_number: int
    title: str
    department: str
    classification: str
    owner: str
    version: str | None
    effective_date: str | None
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Evidence:
    document_id: str
    chunk_id: str
    title: str
    page_number: int
    content: str
    department: str
    classification: str
    owner: str
    version: str | None
    effective_date: str | None
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)