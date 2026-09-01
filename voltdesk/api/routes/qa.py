"""Knowledge Q&A routes.

Owned by: Phase 1 (route signatures). Phase 3 implements the bodies.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from voltdesk.contracts.retrieval import RetrievalAnswer, RetrievalQuery

router = APIRouter(prefix="/qa", tags=["qa"])

_PHASE_3 = "implemented in Phase 3 - see docs/PHASE_3.md"


@router.post("/ask", response_model=RetrievalAnswer)
async def ask(query: RetrievalQuery) -> RetrievalAnswer:
    """Answer a staff question with citations, or abstain explicitly.

    An abstention is a 200, not an error: the system did its job.
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"ask is {_PHASE_3}")


@router.get("/corpus/stats")
async def corpus_stats() -> dict[str, object]:
    """Chunk and document counts per corpus source."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"corpus_stats is {_PHASE_3}")
