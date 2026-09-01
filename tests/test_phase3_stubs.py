"""Phase 3's stubs fail loudly and name their phase. Owned by Phase 1."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from voltdesk.contracts.retrieval import Chunk, CorpusSource, RetrievalQuery
from voltdesk.ingestion.chunking import chunk_document
from voltdesk.ingestion.corpus import (
    CorpusDocumentRecord,
    InMemoryCorpusStore,
    ingest_path,
)
from voltdesk.ingestion.embeddings import Embedder, store_chunks
from voltdesk.retrieval.abstention import abstention_reason, support_score
from voltdesk.retrieval.search import retrieve
from voltdesk.retrieval.synthesis import synthesise, verify_citations

pytestmark = pytest.mark.phase3


def _query() -> RetrievalQuery:
    return RetrievalQuery(query_id="q1", question="What is the export limit?")


def test_chunking_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 3"):
        chunk_document(None)  # type: ignore[arg-type]


def test_embedding_storage_records_model_and_dimension() -> None:
    store = InMemoryCorpusStore()

    class _Embedder(Embedder):
        model_id = "test-embedding"
        dimension = 2

        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

    document = CorpusDocumentRecord(
        document_id="doc-1",
        title="Title",
        source=CorpusSource.REGULATOR_METHODOLOGY,
        source_url="https://example.test/source",
        licence="CC BY 4.0",
        retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
        sha256="a" * 64,
    )
    chunk = Chunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        source=CorpusSource.REGULATOR_METHODOLOGY,
        document_title="Title",
        text="Verified content.",
        section_path=["1. Eligibility"],
        token_count=2,
    )
    assert store_chunks([chunk], _Embedder(), document=document, store=store) == 1
    assert store.embedding_model_id == "test-embedding"
    assert store.dimension == 2


def test_corpus_ingestion_is_licence_gated_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "source.md"
    path.write_text("# 1. Eligibility\n\nVerified content.", encoding="utf-8")
    store = InMemoryCorpusStore()

    class _Embedder(Embedder):
        model_id = "test-embedding"
        dimension = 2

        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

    chunk = Chunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        source=CorpusSource.REGULATOR_METHODOLOGY,
        document_title="Title",
        text="Verified content.",
        section_path=["1. Eligibility"],
        token_count=2,
    )
    monkeypatch.setattr("voltdesk.ingestion.corpus.chunk_document", lambda _doc: [chunk])

    with pytest.raises(ValueError, match="verified licence"):
        ingest_path(str(path), CorpusSource.REGULATOR_METHODOLOGY, "Title")

    kwargs = {
        "source_url": "https://example.test/source",
        "licence": "CC BY 4.0",
        "retrieved_at": datetime(2026, 9, 1, tzinfo=UTC),
        "document_id": "doc-1",
        "embedder": _Embedder(),
        "store": store,
    }
    assert ingest_path(str(path), CorpusSource.REGULATOR_METHODOLOGY, "Title", **kwargs) == 1
    assert ingest_path(str(path), CorpusSource.REGULATOR_METHODOLOGY, "Title", **kwargs) == 0


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
