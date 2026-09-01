"""Retrieval over the corpus.

Owned by: Phase 3. See docs/PHASE_3.md.

Vector similarity alone under-retrieves on this corpus: staff ask about specific
clause numbers, model numbers and standard identifiers, and those are exact-match
lookups that embeddings blur. Combine vector search with a lexical search over the
same chunks. Whatever the mix, the retriever must return `RetrievedChunk` with the
score it actually used, because the abstention scorer reads it.
"""

from __future__ import annotations

from voltdesk.contracts.retrieval import RetrievalQuery, RetrievedChunk


def retrieve(query: RetrievalQuery) -> list[RetrievedChunk]:
    raise NotImplementedError(
        "retrieve is implemented in Phase 3 (docs/PHASE_3.md, step 4)"
    )
