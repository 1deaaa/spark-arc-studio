from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ImportWarning:
    code: str
    message: str


@dataclass(slots=True)
class DocumentSection:
    text: str
    section_type: str = "section"
    title: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    estimated_tokens: int = 0


@dataclass(slots=True)
class ParsedDocument:
    filename: str
    source_format: str
    full_text: str
    sections: list[DocumentSection] = field(default_factory=list)
    warnings: list[ImportWarning] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
