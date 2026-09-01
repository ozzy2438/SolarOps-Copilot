"""Site assessment notes parser.

Owned by: Phase 2. See docs/PHASE_2.md.

These are often photographs of handwriting. The parser must record `used_ocr=True`
and a low-confidence warning rather than silently returning empty text - an empty
extraction that looks clean is worse than a loud parse failure.
"""

from __future__ import annotations

from voltdesk.contracts.common import DocumentType
from voltdesk.parsers.base import DocumentParser, ParsedDocument, ParsedPage
from voltdesk.parsers.pdf_io import (
    extract_pdf_pages,
    looks_like_pdf,
    page_rotation_degrees,
    sha256_hex,
)


class SiteNotesParser(DocumentParser):
    document_type = DocumentType.SITE_ASSESSMENT

    def parse(self, document_id: str, content: bytes, filename: str) -> ParsedDocument:
        lower = filename.lower()
        if looks_like_pdf(content):
            return self._pdf(document_id, content)
        if lower.endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")):
            return ParsedDocument(
                document_id=document_id,
                document_type=self.document_type,
                sha256=sha256_hex(content),
                pages=[
                    ParsedPage(
                        page_number=1,
                        text="",
                        tables=[],
                        used_ocr=True,
                    )
                ],
                warnings=["ocr_unavailable", "image_site_notes"],
            )
        text = content.decode("utf-8", errors="replace")
        warnings: list[str] = []
        if not text.strip():
            warnings.append("empty_site_notes")
        return ParsedDocument(
            document_id=document_id,
            document_type=self.document_type,
            sha256=sha256_hex(content),
            pages=[ParsedPage(page_number=1, text=text, tables=[], used_ocr=False)],
            warnings=warnings,
        )

    def _pdf(self, document_id: str, content: bytes) -> ParsedDocument:
        rotations = page_rotation_degrees(content)
        raw_pages = extract_pdf_pages(content)
        warnings: list[str] = []
        pages: list[ParsedPage] = []
        for index, ((text, tables, used_ocr), rotation) in enumerate(
            zip(raw_pages, rotations, strict=False)
        ):
            if used_ocr and not text:
                warnings.append("ocr_unavailable")
            pages.append(
                ParsedPage(
                    page_number=index + 1,
                    text=text,
                    tables=tables,
                    used_ocr=used_ocr,
                    skew_degrees=None if rotation in (None, 0.0) else rotation,
                )
            )
        if not pages:
            warnings.append("empty_site_notes")
            pages = [ParsedPage(page_number=1, text="", tables=[], used_ocr=True)]
        return ParsedDocument(
            document_id=document_id,
            document_type=self.document_type,
            sha256=sha256_hex(content),
            pages=pages,
            warnings=sorted(set(warnings)),
        )
