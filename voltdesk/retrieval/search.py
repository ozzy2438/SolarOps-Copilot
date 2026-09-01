"""Hybrid lexical and vector retrieval over the Tier A corpus."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Protocol

from sqlalchemy import text

from voltdesk.contracts.retrieval import Chunk, CorpusSource, RetrievalQuery, RetrievedChunk
from voltdesk.db.session import get_engine
from voltdesk.ingestion.embeddings import Embedder, default_embedder

_RRF_K = 60
_IDENTIFIER = re.compile(r"\b(?:[A-Za-z0-9]+[-/.])+[A-Za-z0-9]+\b")


class RetrievalBackend(Protocol):
    """Two ordered candidate channels consumed by reciprocal-rank fusion."""

    def lexical_candidates(self, query: RetrievalQuery, limit: int) -> list[Chunk]: ...

    def vector_candidates(
        self,
        query: RetrievalQuery,
        query_vector: list[float],
        *,
        embedding_model_id: str,
        dimension: int,
        limit: int,
    ) -> list[Chunk]: ...


def _chunk_from_row(mapping: Any) -> Chunk:
    return Chunk(
        chunk_id=mapping["chunk_id"],
        document_id=mapping["document_id"],
        source=CorpusSource(mapping["source"]),
        document_title=mapping["document_title"],
        text=mapping["text"],
        page=mapping["page"],
        section_path=list(mapping["section_path"]),
        token_count=mapping["token_count"],
    )


def _source_parameters(query: RetrievalQuery) -> dict[str, object]:
    return {
        "filter_disabled": not query.source_filter,
        "sources": [source.value for source in query.source_filter],
    }


class PostgresRetrievalBackend:
    """Uses the GIN lexical index and pgvector cosine distance."""

    _columns = (
        "c.chunk_id, c.document_id, d.source, d.title AS document_title, "
        "c.text, c.page, c.section_path, c.token_count"
    )

    def lexical_candidates(self, query: RetrievalQuery, limit: int) -> list[Chunk]:
        identifiers = sorted(_IDENTIFIER.findall(query.question), key=len, reverse=True)
        parameters = {
            "question": query.question,
            "identifier": identifiers[0] if identifiers else "",
            "limit": limit,
            **_source_parameters(query),
        }
        statement = text(
            f"SELECT {self._columns}, "
            "ts_rank_cd(to_tsvector('english', c.text), "
            "websearch_to_tsquery('english', :question)) + "
            "CASE WHEN :identifier <> '' AND "
            "POSITION(lower(:identifier) IN lower(c.text)) > 0 THEN 1 ELSE 0 END "
            "AS lexical_score "
            "FROM vec.chunks AS c "
            "JOIN vec.corpus_documents AS d ON d.id = c.document_id "
            "WHERE (to_tsvector('english', c.text) @@ "
            "websearch_to_tsquery('english', :question) "
            "OR (:identifier <> '' AND "
            "POSITION(lower(:identifier) IN lower(c.text)) > 0)) "
            "AND (:filter_disabled OR d.source = ANY(CAST(:sources AS text[]))) "
            "ORDER BY lexical_score DESC, c.chunk_id ASC LIMIT :limit"
        )
        with get_engine().connect() as connection:
            return [
                _chunk_from_row(row._mapping)
                for row in connection.execute(statement, parameters)
            ]

    def vector_candidates(
        self,
        query: RetrievalQuery,
        query_vector: list[float],
        *,
        embedding_model_id: str,
        dimension: int,
        limit: int,
    ) -> list[Chunk]:
        parameters = {
            "embedding": "[" + ",".join(str(value) for value in query_vector) + "]",
            "model_id": embedding_model_id,
            "dimension": dimension,
            "limit": limit,
            **_source_parameters(query),
        }
        statement = text(
            f"SELECT {self._columns}, "
            "e.embedding <=> CAST(:embedding AS vector) AS vector_distance "
            "FROM vec.embeddings AS e "
            "JOIN vec.chunks AS c ON c.chunk_id = e.chunk_id "
            "JOIN vec.corpus_documents AS d ON d.id = c.document_id "
            "WHERE e.embedding_model_id = :model_id AND e.dimension = :dimension "
            "AND (:filter_disabled OR d.source = ANY(CAST(:sources AS text[]))) "
            "ORDER BY vector_distance ASC, c.chunk_id ASC LIMIT :limit"
        )
        with get_engine().connect() as connection:
            return [
                _chunk_from_row(row._mapping)
                for row in connection.execute(statement, parameters)
            ]


def reciprocal_rank_fusion(
    lexical: Sequence[Chunk], vector: Sequence[Chunk], top_k: int
) -> list[RetrievedChunk]:
    """Fuse ordered channels and expose the normalized RRF score actually used."""
    by_id = {chunk.chunk_id: chunk for chunk in [*lexical, *vector]}
    lexical_rank = {chunk.chunk_id: rank for rank, chunk in enumerate(lexical, start=1)}
    vector_rank = {chunk.chunk_id: rank for rank, chunk in enumerate(vector, start=1)}
    maximum = 2 / (_RRF_K + 1)

    def score(chunk_id: str) -> float:
        raw = 0.0
        if chunk_id in lexical_rank:
            raw += 1 / (_RRF_K + lexical_rank[chunk_id])
        if chunk_id in vector_rank:
            raw += 1 / (_RRF_K + vector_rank[chunk_id])
        return raw / maximum

    ordered = sorted(by_id, key=lambda chunk_id: (-score(chunk_id), chunk_id))[:top_k]
    return [
        RetrievedChunk(chunk=by_id[chunk_id], score=score(chunk_id), rank=rank)
        for rank, chunk_id in enumerate(ordered, start=1)
    ]


def retrieve(
    query: RetrievalQuery,
    *,
    backend: RetrievalBackend | None = None,
    embedder: Embedder | None = None,
) -> list[RetrievedChunk]:
    """Return RRF-ranked chunks from lexical and compatible-vector searches."""
    selected_backend = backend or PostgresRetrievalBackend()
    selected_embedder = embedder or default_embedder()
    query_vectors = selected_embedder.embed([query.question])
    if len(query_vectors) != 1 or len(query_vectors[0]) != selected_embedder.dimension:
        raise ValueError("query embedder returned an invalid vector")
    candidate_limit = max(20, query.top_k * 4)
    lexical = selected_backend.lexical_candidates(query, candidate_limit)
    vector = selected_backend.vector_candidates(
        query,
        query_vectors[0],
        embedding_model_id=selected_embedder.model_id,
        dimension=selected_embedder.dimension,
        limit=candidate_limit,
    )
    return reciprocal_rank_fusion(lexical, vector, query.top_k)
