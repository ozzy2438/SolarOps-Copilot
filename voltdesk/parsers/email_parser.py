"""Email thread parser.

Owned by: Phase 2. See docs/PHASE_2.md.

Trap: quoted history. A five-message thread parsed naively yields the first message
five times. Deduplicate quoted blocks before extraction or the model will summarise
the same content repeatedly and the token cost will scale quadratically.
"""

from __future__ import annotations

from voltdesk.contracts.common import DocumentType
from voltdesk.parsers.base import DocumentParser, ParsedDocument


class EmailThreadParser(DocumentParser):
    document_type = DocumentType.EMAIL_THREAD

    def parse(self, document_id: str, content: bytes, filename: str) -> ParsedDocument:
        raise NotImplementedError(
            "EmailThreadParser.parse is implemented in Phase 2 (docs/PHASE_2.md, step 2)"
        )
