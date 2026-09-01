"""Document parsers. Owned by Phase 2; contracts fixed in Phase 1."""

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
]
