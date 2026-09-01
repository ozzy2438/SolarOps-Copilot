"""Electricity bill parser.

Owned by: Phase 2. See docs/PHASE_2.md.

Known traps, from the synthetic generator's deliberate defects (docs/DATA_SOURCES.md):
two retailers with different layouts, multi-page bills where the tariff table
continues across a page break, skewed scans needing OCR, and both DD/MM/YYYY and
D Mon YYYY date formats in the same corpus.
"""

from __future__ import annotations

from voltdesk.contracts.common import DocumentType
from voltdesk.parsers.base import DocumentParser, ParsedDocument, ParsedPage
from voltdesk.parsers.pdf_io import (
    extract_pdf_pages,
    looks_like_pdf,
    page_rotation_degrees,
    sha256_hex,
    stitch_split_tables,
)

_DATE_DMY = r"\b\d{1,2}/\d{1,2}/\d{4}\b"
_DATE_MON = r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b"


class BillParser(DocumentParser):
    document_type = DocumentType.ELECTRICITY_BILL

    def parse(self, document_id: str, content: bytes, filename: str) -> ParsedDocument:
        warnings: list[str] = []
        if not looks_like_pdf(content):
            text = content.decode("utf-8", errors="replace")
            return ParsedDocument(
                document_id=document_id,
                document_type=self.document_type,
                sha256=sha256_hex(content),
                pages=[ParsedPage(page_number=1, text=text, tables=[], used_ocr=False)],
                warnings=_date_warnings(text),
            )

        rotations = page_rotation_degrees(content)
        raw_pages = extract_pdf_pages(content)
        tables_only = [tables for _, tables, _ in raw_pages]
        stitched = stitch_split_tables(tables_only)
        pages: list[ParsedPage] = []
        for index, ((text, _, used_ocr), tables, rotation) in enumerate(
            zip(raw_pages, stitched, rotations, strict=False)
        ):
            if used_ocr and not text:
                warnings.append("ocr_unavailable")
            if rotation not in (None, 0.0):
                warnings.append(f"page_{index + 1}_rotated_{rotation:.0f}_deg")
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
            pages = [
                ParsedPage(
                    page_number=1,
                    text="",
                    tables=[],
                    used_ocr=True,
                )
            ]
            warnings.append("empty_pdf")
        warnings.extend(_date_warnings("\n".join(page.text for page in pages)))
        return ParsedDocument(
            document_id=document_id,
            document_type=self.document_type,
            sha256=sha256_hex(content),
            pages=pages,
            warnings=sorted(set(warnings)),
        )


def _date_warnings(text: str) -> list[str]:
    import re

    has_dmy = re.search(_DATE_DMY, text) is not None
    has_mon = re.search(_DATE_MON, text, re.IGNORECASE) is not None
    if has_dmy and has_mon:
        return ["ambiguous_date_formats"]
    return []
