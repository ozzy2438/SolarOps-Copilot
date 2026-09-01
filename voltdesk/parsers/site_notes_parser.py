"""Site assessment notes parser.

Owned by: Phase 2. See docs/PHASE_2.md.

These are often photographs of handwriting. The parser must record `used_ocr=True`
and a low-confidence warning rather than silently returning empty text - an empty
extraction that looks clean is worse than a loud parse failure.
"""

from __future__ import annotations

from voltdesk.contracts.common import DocumentType
from voltdesk.parsers.base import DocumentParser, ParsedDocument


class SiteNotesParser(DocumentParser):
    document_type = DocumentType.SITE_ASSESSMENT

    def parse(self, document_id: str, content: bytes, filename: str) -> ParsedDocument:
        raise NotImplementedError(
            "SiteNotesParser.parse is implemented in Phase 2 (docs/PHASE_2.md, step 2)"
        )
