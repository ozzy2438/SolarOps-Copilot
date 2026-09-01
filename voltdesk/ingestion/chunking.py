"""Corpus chunking.

Owned by: Phase 3. See docs/PHASE_3.md.

Trap specific to this corpus: the documents are standards, datasheets and connection
guidelines. Their meaning lives in numbered clauses and in tables. A fixed-size
character window cuts a clause in half and makes the retrieved chunk unciteable.
Chunk on structure - heading path and clause boundary - and keep `section_path`
populated, because the citation shows it to the reader.
"""

from __future__ import annotations

from voltdesk.contracts.retrieval import Chunk
from voltdesk.parsers.base import ParsedDocument


def chunk_document(document: ParsedDocument, target_tokens: int = 512) -> list[Chunk]:
    raise NotImplementedError(
        "chunk_document is implemented in Phase 3 (docs/PHASE_3.md, step 2)"
    )
