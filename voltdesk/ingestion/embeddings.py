"""Embedding generation and storage.

Owned by: Phase 3. See docs/PHASE_3.md.

Vectors live in the `vec` schema (migrations/0003_vectors.sql). The embedding model
identity and its dimension are stored alongside every vector: a corpus embedded with
two different models is silently unusable, and the only defence is recording which
model produced each row.

ADR-0015 pins the local Apache-2.0 embedding model and its immutable revision.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from voltdesk.contracts.retrieval import Chunk
from voltdesk.db.session import get_engine

if TYPE_CHECKING:
    from voltdesk.ingestion.corpus import CorpusDocumentRecord, CorpusStore


class Embedder(ABC):
    """Turns chunk text into vectors."""

    model_id: str
    dimension: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class SentenceTransformerEmbedder(Embedder):
    """Lazy, local embedder pinned to the revision recorded by ADR-0015."""

    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    model_revision = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    model_id = f"{model_name}@{model_revision}"
    dimension = 384

    def __init__(self) -> None:
        self._model: Any | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.model_name,
                revision=self.model_revision,
                trust_remote_code=False,
            )
        encoded = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [[float(value) for value in vector] for vector in encoded]


class PostgresCorpusStore:
    """Atomically persists provenance, structural chunks and their vectors."""

    def contains_sha256(self, sha256: str) -> bool:
        with get_engine().connect() as connection:
            return bool(
                connection.execute(
                    text("SELECT 1 FROM vec.corpus_documents WHERE sha256 = :sha256"),
                    {"sha256": sha256},
                ).scalar_one_or_none()
            )

    def write(
        self,
        document: CorpusDocumentRecord,
        chunks: list[Chunk],
        vectors: list[list[float]],
        *,
        embedding_model_id: str,
        dimension: int,
    ) -> int:
        if len(chunks) != len(vectors):
            raise ValueError("one embedding is required for every chunk")
        if any(len(vector) != dimension for vector in vectors):
            raise ValueError(f"embedding dimension must be {dimension}")

        with get_engine().begin() as connection:
            existing = connection.execute(
                text(
                    "SELECT DISTINCT embedding_model_id, dimension "
                    "FROM vec.embeddings LIMIT 2"
                )
            ).all()
            if any(row != (embedding_model_id, dimension) for row in existing):
                raise ValueError("refusing to mix embedding models or dimensions in one corpus")

            inserted = connection.execute(
                text(
                    "INSERT INTO vec.corpus_documents "
                    "(id, title, source, source_url, licence, retrieved_at, sha256) "
                    "VALUES (:id, :title, :source, :source_url, :licence, "
                    ":retrieved_at, :sha256) "
                    "ON CONFLICT (sha256) DO NOTHING"
                ),
                {
                    "id": document.document_id,
                    "title": document.title,
                    "source": document.source.value,
                    "source_url": document.source_url,
                    "licence": document.licence,
                    "retrieved_at": document.retrieved_at,
                    "sha256": document.sha256,
                },
            )
            if inserted.rowcount == 0:
                return 0

            for chunk, vector in zip(chunks, vectors, strict=True):
                connection.execute(
                    text(
                        "INSERT INTO vec.chunks "
                        "(chunk_id, document_id, text, page, section_path, token_count) "
                        "VALUES (:chunk_id, :document_id, :text, :page, "
                        ":section_path, :token_count)"
                    ),
                    {
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "text": chunk.text,
                        "page": chunk.page,
                        "section_path": chunk.section_path,
                        "token_count": chunk.token_count,
                    },
                )
                connection.execute(
                    text(
                        "INSERT INTO vec.embeddings "
                        "(chunk_id, embedding_model_id, dimension, embedding) "
                        "VALUES (:chunk_id, :model_id, :dimension, "
                        "CAST(:embedding AS vector))"
                    ),
                    {
                        "chunk_id": chunk.chunk_id,
                        "model_id": embedding_model_id,
                        "dimension": dimension,
                        "embedding": "[" + ",".join(str(value) for value in vector) + "]",
                    },
                )
        return len(chunks)


def store_chunks(
    chunks: list[Chunk],
    embedder: Embedder,
    *,
    document: CorpusDocumentRecord | None = None,
    store: CorpusStore | None = None,
) -> int:
    """Embed and persist. Returns the number of chunks written."""
    if document is None or store is None:
        raise ValueError("store_chunks requires document provenance and a corpus store")
    vectors = embedder.embed([chunk.text for chunk in chunks])
    if len(vectors) != len(chunks):
        raise ValueError("the embedder must return one vector per chunk")
    for vector in vectors:
        if len(vector) != embedder.dimension:
            raise ValueError(
                f"{embedder.model_id} returned dimension {len(vector)}; "
                f"expected {embedder.dimension}"
            )
    return store.write(
        document,
        chunks,
        vectors,
        embedding_model_id=embedder.model_id,
        dimension=embedder.dimension,
    )


def default_embedder() -> Embedder:
    """Construct the immutable, ADR-selected local embedding model."""
    return SentenceTransformerEmbedder()
