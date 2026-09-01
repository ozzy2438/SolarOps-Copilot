"""Abstention scoring.

Owned by: Phase 3. See docs/PHASE_3.md.

Abstention is a feature of this system, not a failure of it. The company's staff ask
compliance questions; a confident wrong answer about an export limit or a connection
requirement is worse than "I don't have evidence for that".

The scorer produces `support_score` in [0, 1], compared against
VOLTDESK_ABSTENTION_THRESHOLD. Phase 4 measures abstention precision and recall
(docs/EVALUATION.md) and tunes the threshold from the curve, not from intuition.
"""

from __future__ import annotations

from voltdesk.contracts.retrieval import AbstentionReason, RetrievalQuery, RetrievedChunk


def support_score(query: RetrievalQuery, chunks: list[RetrievedChunk]) -> float:
    raise NotImplementedError(
        "support_score is implemented in Phase 3 (docs/PHASE_3.md, step 6)"
    )


def abstention_reason(
    query: RetrievalQuery, chunks: list[RetrievedChunk], score: float
) -> AbstentionReason:
    """Which of the four reasons applies. The user is told this, so it must be true."""
    raise NotImplementedError(
        "abstention_reason is implemented in Phase 3 (docs/PHASE_3.md, step 6)"
    )
