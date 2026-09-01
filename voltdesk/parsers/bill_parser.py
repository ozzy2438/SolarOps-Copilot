"""Electricity bill parser.

Owned by: Phase 2. See docs/PHASE_2.md.

Known traps, from the synthetic generator's deliberate defects (docs/DATA_SOURCES.md):
two retailers with different layouts, multi-page bills where the tariff table
continues across a page break, skewed scans needing OCR, and both DD/MM/YYYY and
D Mon YYYY date formats in the same corpus.
"""

from __future__ import annotations

from voltdesk.contracts.common import DocumentType
from voltdesk.parsers.base import DocumentParser, ParsedDocument


class BillParser(DocumentParser):
    document_type = DocumentType.ELECTRICITY_BILL

    def parse(self, document_id: str, content: bytes, filename: str) -> ParsedDocument:
        raise NotImplementedError(
            "BillParser.parse is implemented in Phase 2 (docs/PHASE_2.md, step 2)"
        )
