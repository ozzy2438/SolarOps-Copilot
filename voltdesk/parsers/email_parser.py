"""Email thread parser.

Owned by: Phase 2. See docs/PHASE_2.md.

Trap: quoted history. A five-message thread parsed naively yields the first message
five times. Deduplicate quoted blocks before extraction or the model will summarise
the same content repeatedly and the token cost will scale quadratically.
"""

from __future__ import annotations

import re
from email import policy
from email.parser import BytesParser

from voltdesk.contracts.common import DocumentType
from voltdesk.parsers.base import DocumentParser, ParsedDocument, ParsedPage
from voltdesk.parsers.pdf_io import sha256_hex

_WROTE = re.compile(r"^On .+ wrote:\s*$")
_QUOTE = re.compile(r"^>+")


class EmailThreadParser(DocumentParser):
    document_type = DocumentType.EMAIL_THREAD

    def parse(self, document_id: str, content: bytes, filename: str) -> ParsedDocument:
        if filename.endswith(".eml"):
            raw = _eml_text(content)
        else:
            raw = content.decode("utf-8", errors="replace")
        cleaned, dropped = dedupe_quoted(raw)
        warnings: list[str] = []
        if dropped:
            warnings.append("quoted_history_deduplicated")
        return ParsedDocument(
            document_id=document_id,
            document_type=self.document_type,
            sha256=sha256_hex(content),
            pages=[ParsedPage(page_number=1, text=cleaned, tables=[], used_ocr=False)],
            warnings=warnings,
        )


def _eml_text(content: bytes) -> str:
    message = BytesParser(policy=policy.default).parsebytes(content)
    parts = [
        f"From: {message.get('From', '')}",
        f"To: {message.get('To', '')}",
        f"Date: {message.get('Date', '')}",
        f"Subject: {message.get('Subject', '')}",
        "",
        message.get_content() if message.is_multipart() is False else _walk(message),
    ]
    return "\n".join(parts)


def _walk(message: object) -> str:
    body = getattr(message, "get_body", lambda **_: None)(preferencelist=("plain", "html"))
    if body is None:
        return ""
    return str(body.get_content())


def dedupe_quoted(text: str) -> tuple[str, bool]:
    """Drop `>` quoted lines and 'On ... wrote:' markers. Also drop a paragraph
    that has already appeared, so a reply that pastes the original in full does
    not give the extractor five copies of the first message.
    """
    kept: list[str] = []
    dropped = False
    seen: set[str] = set()
    buffer: list[str] = []

    def _flush() -> None:
        nonlocal dropped
        paragraph = "\n".join(buffer).strip()
        buffer.clear()
        if not paragraph:
            return
        key = re.sub(r"\s+", " ", paragraph).lower()
        if key in seen:
            dropped = True
            return
        seen.add(key)
        kept.append(paragraph)

    for line in text.splitlines():
        if _QUOTE.match(line) or _WROTE.match(line):
            dropped = True
            continue
        if not line.strip():
            _flush()
            continue
        buffer.append(line.rstrip())
    _flush()
    return "\n\n".join(kept), dropped
