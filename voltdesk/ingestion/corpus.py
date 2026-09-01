"""Corpus ingestion pipeline.

Owned by: Phase 3. See docs/PHASE_3.md.

Tier A only. Every corpus document must have a licence recorded in
docs/DATA_SOURCES.md before it is ingested; a document with an unverified source is
not ingested and its TODO stays open. Ingesting a document VoltDesk has no right to
redistribute is the one failure here that cannot be fixed by a later phase.
"""

from __future__ import annotations

from voltdesk.contracts.retrieval import CorpusSource


def ingest_path(path: str, source: CorpusSource, document_title: str) -> int:
    """Parse, chunk, embed and store one corpus document. Returns chunks written."""
    raise NotImplementedError(
        "ingest_path is implemented in Phase 3 (docs/PHASE_3.md, step 1)"
    )
