"""Human review queue.

Owned by: Phase 2. See docs/PHASE_2.md.

The queue is a table, not a message broker: a reviewer needs to see what is
outstanding, and outstanding items must survive a restart. Redis holds jobs, not
review state.
"""

from __future__ import annotations

from typing import Any

from voltdesk.contracts.review import ReviewItem


class ReviewQueue:
    """CRUD over app.review_queue."""

    def enqueue(self, item: ReviewItem) -> str:
        raise NotImplementedError(
            "ReviewQueue.enqueue is implemented in Phase 2 (docs/PHASE_2.md, step 8)"
        )

    def list_pending(self, limit: int = 50, offset: int = 0) -> list[ReviewItem]:
        raise NotImplementedError(
            "ReviewQueue.list_pending is implemented in Phase 2 (docs/PHASE_2.md, step 8)"
        )

    def get(self, review_id: str) -> ReviewItem:
        raise NotImplementedError(
            "ReviewQueue.get is implemented in Phase 2 (docs/PHASE_2.md, step 8)"
        )

    def resolve(
        self, review_id: str, corrections: dict[str, Any], resolved_by: str
    ) -> ReviewItem:
        """Apply a reviewer's corrections and, if the item was blocking, release the
        CRM write. Corrections are retained - Phase 4 mines them as ground truth."""
        raise NotImplementedError(
            "ReviewQueue.resolve is implemented in Phase 2 (docs/PHASE_2.md, step 8)"
        )
