"""Review queue. Owned by: Phase 2. No database required."""

from __future__ import annotations

from datetime import UTC, datetime

from voltdesk.contracts.common import DocumentType, ReviewStatus
from voltdesk.contracts.review import FieldForReview, ReviewItem
from voltdesk.review.queue import ReviewQueue


def _item(review_id: str = "rev-1") -> ReviewItem:
    return ReviewItem(
        review_id=review_id,
        document_id="doc-1",
        document_type=DocumentType.ELECTRICITY_BILL,
        created_at=datetime(2026, 3, 1, tzinfo=UTC),
        status=ReviewStatus.PENDING_REVIEW,
        fields=[
            FieldForReview(
                field_path="nmi",
                proposed_value="6305888444",
                confidence=0.4,
                reason="The NMI is the join key.",
            )
        ],
        blocking=True,
    )


def test_enqueue_list_and_retain_corrections() -> None:
    queue = ReviewQueue(memory={})
    queue.enqueue(_item())
    pending = queue.list_pending()
    assert len(pending) == 1
    resolved = queue.resolve("rev-1", {"nmi": "6305888445"}, resolved_by="tester")
    assert resolved.status == ReviewStatus.APPROVED
    assert resolved.corrections == {"nmi": "6305888445"}
    assert resolved.resolved_by == "tester"
    assert queue.list_pending() == []
    stored = queue.get("rev-1")
    assert stored.corrections["nmi"] == "6305888445"
