"""Hybrid retrieval tests. No database or network is required."""

from __future__ import annotations

from voltdesk.contracts.retrieval import Chunk, CorpusSource, RetrievalQuery
from voltdesk.ingestion.embeddings import Embedder
from voltdesk.retrieval.search import RetrievalBackend, retrieve


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        source=CorpusSource.REGULATOR_METHODOLOGY,
        document_title=f"Document {chunk_id}",
        text=text,
        page=1,
        section_path=["5. Export control"],
        token_count=len(text.split()),
    )


class _Embedder(Embedder):
    model_id = "test-model@fixed"
    dimension = 2

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class _Backend(RetrievalBackend):
    def __init__(self, lexical: list[Chunk], vector: list[Chunk]) -> None:
        self.lexical = lexical
        self.vector = vector
        self.seen_model: tuple[str, int] | None = None

    def lexical_candidates(self, query: RetrievalQuery, limit: int) -> list[Chunk]:
        return self.lexical[:limit]

    def vector_candidates(
        self,
        query: RetrievalQuery,
        query_vector: list[float],
        *,
        embedding_model_id: str,
        dimension: int,
        limit: int,
    ) -> list[Chunk]:
        self.seen_model = (embedding_model_id, dimension)
        return self.vector[:limit]


def test_lexical_exact_clause_number_wins_hybrid_ranking() -> None:
    exact = _chunk("exact", "Clause 5.3 requires an export control limit of 5 kW.")
    semantic_only = _chunk("semantic", "General guidance about electricity exports.")
    backend = _Backend(lexical=[exact], vector=[semantic_only, exact])
    query = RetrievalQuery(query_id="q1", question="What does clause 5.3 require?", top_k=2)

    results = retrieve(query, backend=backend, embedder=_Embedder())

    assert results[0].chunk.chunk_id == "exact"
    assert results[0].score > results[1].score
    assert results[0].rank == 1


def test_vector_search_is_restricted_to_the_query_model_and_dimension() -> None:
    result = _chunk("result", "Relevant evidence.")
    backend = _Backend(lexical=[], vector=[result])

    retrieve(
        RetrievalQuery(query_id="q1", question="Relevant question"),
        backend=backend,
        embedder=_Embedder(),
    )

    assert backend.seen_model == ("test-model@fixed", 2)


def test_source_filter_is_preserved_for_both_channels() -> None:
    class _FilteringBackend(_Backend):
        def lexical_candidates(self, query: RetrievalQuery, limit: int) -> list[Chunk]:
            assert query.source_filter == [CorpusSource.REGULATOR_METHODOLOGY]
            return super().lexical_candidates(query, limit)

        def vector_candidates(
            self,
            query: RetrievalQuery,
            query_vector: list[float],
            *,
            embedding_model_id: str,
            dimension: int,
            limit: int,
        ) -> list[Chunk]:
            assert query.source_filter == [CorpusSource.REGULATOR_METHODOLOGY]
            return super().vector_candidates(
                query,
                query_vector,
                embedding_model_id=embedding_model_id,
                dimension=dimension,
                limit=limit,
            )

    result = _chunk("result", "Relevant evidence.")
    query = RetrievalQuery(
        query_id="q1",
        question="Relevant question",
        source_filter=[CorpusSource.REGULATOR_METHODOLOGY],
    )
    assert retrieve(query, backend=_FilteringBackend([result], [result]), embedder=_Embedder())
