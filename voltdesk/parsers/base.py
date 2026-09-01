"""Document parsing: bytes -> text and layout.

Owned by: Phase 2. Signatures and the contract are fixed here in Phase 1.

Parsing is separate from extraction on purpose. A parser produces text plus layout
hints and never calls a model; an extractor calls a model and never opens a file.
Keeping them apart is what lets Phase 4 measure extraction quality without a PDF
library in the loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import Field

from voltdesk.contracts.common import DocumentType, StrictModel


class ParsedPage(StrictModel):
    """One page of a parsed document."""

    page_number: int = Field(ge=1)
    text: str
    #: Rows of any table detected on the page, as lists of cell strings. Datasheets and
    #: bills carry their real content in tables; flattening them loses the association
    #: between a rate and its label.
    tables: list[list[list[str]]] = Field(default_factory=list)
    used_ocr: bool = Field(default=False, description="True when the text layer was absent.")
    skew_degrees: float | None = Field(default=None, description="Detected rotation, if any.")


class ParsedDocument(StrictModel):
    """A parsed document, ready for extraction."""

    document_id: str
    document_type: DocumentType
    sha256: str = Field(min_length=64, max_length=64)
    pages: list[ParsedPage] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)

    def full_text(self) -> str:
        """Pages joined with a form feed, so a model can still see page boundaries."""
        return "\f".join(page.text for page in self.pages)


class DocumentParser(ABC):
    """Turns raw bytes into a ParsedDocument. Never calls a model."""

    document_type: DocumentType

    @abstractmethod
    def parse(self, document_id: str, content: bytes, filename: str) -> ParsedDocument:
        raise NotImplementedError("DocumentParser subclass must implement parse")
