"""Document parsers. Owned by Phase 2; contracts fixed in Phase 1."""

from voltdesk.contracts.common import DocumentType
from voltdesk.parsers.base import DocumentParser, ParsedDocument, ParsedPage
from voltdesk.parsers.bill_parser import BillParser
from voltdesk.parsers.email_parser import EmailThreadParser
from voltdesk.parsers.site_notes_parser import SiteNotesParser

__all__ = [
    "BillParser",
    "DocumentParser",
    "EmailThreadParser",
    "ParsedDocument",
    "ParsedPage",
    "SiteNotesParser",
    "parser_for",
]


def parser_for(document_type: DocumentType) -> DocumentParser:
    mapping: dict[DocumentType, DocumentParser] = {
        DocumentType.ELECTRICITY_BILL: BillParser(),
        DocumentType.SITE_ASSESSMENT: SiteNotesParser(),
        DocumentType.EMAIL_THREAD: EmailThreadParser(),
    }
    return mapping[document_type]
