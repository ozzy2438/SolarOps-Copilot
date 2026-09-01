"""Phase 3's stubs fail loudly and name their phase. Owned by Phase 1."""

from __future__ import annotations

import pytest

from voltdesk.contracts.retrieval import CorpusSource, RetrievalQuery
from voltdesk.ingestion.chunking import chunk_document
from voltdesk.ingestion.corpus import ingest_path
from voltdesk.ingestion.embeddings import store_chunks
from voltdesk.retrieval.abstention import abstention_reason, support_score
from voltdesk.retrieval.search import retrieve
from voltdesk.retrieval.synthesis import synthesise, verify_citations

pytestmark = pytest.mark.phase3


def _query() -> RetrievalQuery:
    return RetrievalQuery(query_id="q1", question="What is the export limit?")


def test_chunking_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 3"):
        chunk_document(None)  # type: ignore[arg-type]


def test_embedding_storage_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 3"):
        store_chunks([], None)  # type: ignore[arg-type]


def test_corpus_ingestion_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 3"):
        ingest_path("x.pdf", CorpusSource.INTERNAL_STANDARD, "Title")


def test_retrieval_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 3"):
        retrieve(_query())


def test_synthesis_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 3"):
        synthesise(_query(), [])
    with pytest.raises(NotImplementedError, match="Phase 3"):
        verify_citations(None, [])  # type: ignore[arg-type]


def test_abstention_scoring_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 3"):
        support_score(_query(), [])
    with pytest.raises(NotImplementedError, match="Phase 3"):
        abstention_reason(_query(), [], 0.1)
