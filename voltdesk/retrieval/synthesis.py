"""Citation-grounded answer synthesis.

Owned by: Phase 3. See docs/PHASE_3.md.

The hard requirement: every citation's `quote` must appear verbatim in the chunk it
names. Phase 3 verifies this after synthesis and before returning. A model that
paraphrases a quote has produced an unverifiable citation, and an unverifiable
citation invalidates the answer - the correct response is to abstain, not to return
the answer with a warning.
"""

from __future__ import annotations

from voltdesk.contracts.retrieval import RetrievalAnswer, RetrievalQuery, RetrievedChunk


def synthesise(query: RetrievalQuery, chunks: list[RetrievedChunk]) -> RetrievalAnswer:
    raise NotImplementedError(
        "synthesise is implemented in Phase 3 (docs/PHASE_3.md, step 5)"
    )


def verify_citations(answer: RetrievalAnswer, chunks: list[RetrievedChunk]) -> bool:
    """True when every citation quote appears verbatim in its named chunk."""
    raise NotImplementedError(
        "verify_citations is implemented in Phase 3 (docs/PHASE_3.md, step 5)"
    )
