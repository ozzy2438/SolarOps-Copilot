"""Embedding generation and storage.

Owned by: Phase 3. See docs/PHASE_3.md.

Vectors live in the `vec` schema (migrations/0003_vectors.sql). The embedding model
identity and its dimension are stored alongside every vector: a corpus embedded with
two different models is silently unusable, and the only defence is recording which
model produced each row.

TODO(verify): the embedding model has not been chosen. Phase 3 chooses it, records
an ADR, and sets the dimension in the migration accordingly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from voltdesk.contracts.retrieval import Chunk

if TYPE_CHECKING:
    from voltdesk.ingestion.corpus import CorpusDocumentRecord, CorpusStore


class Embedder(ABC):
    """Turns chunk text into vectors."""

    model_id: str
    dimension: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            "Embedder.embed is implemented in Phase 3 (docs/PHASE_3.md, step 3)"
        )


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
    """Construct the ADR-selected embedder after Phase 3 step 3 configures it."""
    raise RuntimeError("the Phase 3 embedding model has not been configured yet")
