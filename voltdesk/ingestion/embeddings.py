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

from voltdesk.contracts.retrieval import Chunk


class Embedder(ABC):
    """Turns chunk text into vectors."""

    model_id: str
    dimension: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            "Embedder.embed is implemented in Phase 3 (docs/PHASE_3.md, step 3)"
        )


def store_chunks(chunks: list[Chunk], embedder: Embedder) -> int:
    """Embed and persist. Returns the number of chunks written."""
    raise NotImplementedError(
        "store_chunks is implemented in Phase 3 (docs/PHASE_3.md, step 3)"
    )
