"""Corpus chunking.

Owned by: Phase 3. See docs/PHASE_3.md.

Trap specific to this corpus: the documents are standards, datasheets and connection
guidelines. Their meaning lives in numbered clauses and in tables. A fixed-size
character window cuts a clause in half and makes the retrieved chunk unciteable.
Chunk on structure - heading path and clause boundary - and keep `section_path`
populated, because the citation shows it to the reader.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from voltdesk.contracts.retrieval import Chunk, CorpusSource
from voltdesk.parsers.base import ParsedDocument, ParsedPage

_MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_NUMBERED_CLAUSE = re.compile(r"^\s*((?:\d+\.)*\d+)(?:[.)]|\s+)\s*(\S.*)$")


@dataclass(frozen=True)
class _Block:
    text: str
    page: int
    section_path: list[str]


def _token_count(text: str) -> int:
    return max(1, len(re.findall(r"\S+", text)))


def _chunk_id(document: ParsedDocument, block: _Block) -> str:
    identity = "\x00".join(
        [document.sha256, str(block.page), "/".join(block.section_path), block.text]
    )
    return f"chunk-{hashlib.sha256(identity.encode()).hexdigest()[:24]}"


def _page_blocks(page: ParsedPage, fallback_path: list[str]) -> list[_Block]:
    blocks: list[_Block] = []
    heading_stack: list[str] = []
    clause_stack: list[str] = []
    current_path = fallback_path
    lines: list[str] = []

    def flush() -> None:
        nonlocal lines
        text = "\n".join(lines).strip()
        if text:
            blocks.append(_Block(text=text, page=page.page_number, section_path=current_path))
        lines = []

    for line in page.text.splitlines():
        heading = _MARKDOWN_HEADING.match(line)
        clause = _NUMBERED_CLAUSE.match(line) if not line.lstrip().startswith("|") else None
        if heading:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_stack[level - 1 :] = [title]
            clause_stack = []
            current_path = heading_stack.copy()
            lines.append(line)
            continue
        if clause:
            flush()
            label = f"{clause.group(1)} {clause.group(2).strip()}"
            depth = clause.group(1).count(".") + 1
            clause_stack[depth - 1 :] = [label]
            current_path = [*heading_stack, *clause_stack] or fallback_path
            lines.append(line)
            continue
        lines.append(line)
    flush()

    for table_number, table in enumerate(page.tables, start=1):
        rows = [" | ".join(cell.strip() for cell in row) for row in table if row]
        if not rows:
            continue
        table_text = "\n".join(rows)
        if table_text in page.text:
            continue
        blocks.append(
            _Block(
                text=table_text,
                page=page.page_number,
                section_path=[*heading_stack, f"Table {table_number}"] or fallback_path,
            )
        )
    return blocks


def chunk_document(
    document: ParsedDocument,
    target_tokens: int = 512,
    *,
    source: CorpusSource = CorpusSource.INTERNAL_STANDARD,
    document_title: str | None = None,
) -> list[Chunk]:
    """Return structural chunks; target size never overrides a clause or table boundary."""
    if target_tokens < 1:
        raise ValueError("target_tokens must be positive")
    title = document_title or document.document_id
    fallback_path = [title]
    blocks = [
        block
        for page in document.pages
        for block in _page_blocks(page, fallback_path=fallback_path)
    ]
    return [
        Chunk(
            chunk_id=_chunk_id(document, block),
            document_id=document.document_id,
            source=source,
            document_title=title,
            text=block.text,
            page=block.page,
            section_path=block.section_path or fallback_path,
            token_count=_token_count(block.text),
        )
        for block in blocks
    ]
