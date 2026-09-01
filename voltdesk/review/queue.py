"""Human review queue.

Owned by: Phase 2. See docs/PHASE_2.md.

The queue is a table, not a message broker: a reviewer needs to see what is
outstanding, and outstanding items must survive a restart. Redis holds jobs, not
review state.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, text

from voltdesk.config import get_settings
from voltdesk.contracts.common import DocumentType, ReviewStatus
from voltdesk.contracts.review import FieldForReview, ReviewItem
from voltdesk.db.session import get_engine

_PROCESS_MEMORY: dict[str, ReviewItem] = {}

_INSERT = text(
    """
    INSERT INTO app.review_queue (
        review_id, document_id, document_type, status, blocking, fields, corrections,
        created_at, resolved_at, resolved_by
    ) VALUES (
        :review_id, :document_id, :document_type, :status, :blocking,
        CAST(:fields AS jsonb), CAST(:corrections AS jsonb),
        :created_at, :resolved_at, :resolved_by
    )
    """
)
_LIST = text(
    """
    SELECT * FROM app.review_queue
    WHERE status = 'pending_review'
    ORDER BY created_at
    LIMIT :limit OFFSET :offset
    """
)
_GET = text("SELECT * FROM app.review_queue WHERE review_id = :review_id")
_RESOLVE = text(
    """
    UPDATE app.review_queue
    SET status = :status,
        corrections = CAST(:corrections AS jsonb),
        resolved_at = :resolved_at,
        resolved_by = :resolved_by
    WHERE review_id = :review_id AND status = 'pending_review'
    """
)


class ReviewNotFoundError(KeyError):
    """No review item with that id."""


class ReviewQueue:
    """CRUD over app.review_queue, or a process-local dict when no database is configured."""

    def __init__(
        self,
        engine: Engine | None = None,
        memory: dict[str, ReviewItem] | None = None,
    ) -> None:
        self._engine = engine
        self._memory = memory
        if self._memory is None and engine is None:
            if "not-configured" in get_settings().database_url:
                self._memory = _PROCESS_MEMORY

    def enqueue(self, item: ReviewItem) -> str:
        if self._memory is not None:
            self._memory[item.review_id] = item
            return item.review_id
        with self._engine_or_default().begin() as connection:
            connection.execute(_INSERT, _row(item))
        return item.review_id

    def list_pending(self, limit: int = 50, offset: int = 0) -> list[ReviewItem]:
        if self._memory is not None:
            pending = [
                item
                for item in self._memory.values()
                if item.status == ReviewStatus.PENDING_REVIEW
            ]
            pending.sort(key=lambda item: item.created_at)
            return pending[offset : offset + limit]
        with self._engine_or_default().connect() as connection:
            rows = connection.execute(_LIST, {"limit": limit, "offset": offset}).mappings()
            return [_from_row(dict(row)) for row in rows]

    def get(self, review_id: str) -> ReviewItem:
        if self._memory is not None:
            try:
                return self._memory[review_id]
            except KeyError as exc:
                raise ReviewNotFoundError(review_id) from exc
        with self._engine_or_default().connect() as connection:
            row = connection.execute(_GET, {"review_id": review_id}).mappings().first()
        if row is None:
            raise ReviewNotFoundError(review_id)
        return _from_row(dict(row))

    def resolve(
        self, review_id: str, corrections: dict[str, Any], resolved_by: str
    ) -> ReviewItem:
        """Apply a reviewer's corrections and, if the item was blocking, release the
        CRM write. Corrections are retained - Phase 4 mines them as ground truth."""
        now = datetime.now(UTC)
        if self._memory is not None:
            item = self.get(review_id)
            updated = item.model_copy(
                update={
                    "status": ReviewStatus.APPROVED,
                    "corrections": corrections,
                    "resolved_at": now,
                    "resolved_by": resolved_by,
                }
            )
            self._memory[review_id] = updated
            return updated
        with self._engine_or_default().begin() as connection:
            result = connection.execute(
                _RESOLVE,
                {
                    "review_id": review_id,
                    "status": str(ReviewStatus.APPROVED),
                    "corrections": json.dumps(corrections),
                    "resolved_at": now,
                    "resolved_by": resolved_by,
                },
            )
            if result.rowcount == 0:
                raise ReviewNotFoundError(review_id)
        return self.get(review_id)

    def _engine_or_default(self) -> Engine:
        return self._engine or get_engine()


def new_review_item(
    *,
    document_id: str,
    document_type: DocumentType,
    fields: list[FieldForReview],
    blocking: bool,
) -> ReviewItem:
    return ReviewItem(
        review_id=str(uuid.uuid4()),
        document_id=document_id,
        document_type=document_type,
        created_at=datetime.now(UTC),
        status=ReviewStatus.PENDING_REVIEW,
        fields=fields,
        blocking=blocking,
    )


def _row(item: ReviewItem) -> dict[str, Any]:
    return {
        "review_id": item.review_id,
        "document_id": item.document_id,
        "document_type": str(item.document_type),
        "status": str(item.status),
        "blocking": item.blocking,
        "fields": json.dumps([field.model_dump(mode="json") for field in item.fields]),
        "corrections": json.dumps(item.corrections),
        "created_at": item.created_at,
        "resolved_at": item.resolved_at,
        "resolved_by": item.resolved_by,
    }


def _from_row(row: dict[str, Any]) -> ReviewItem:
    fields = row["fields"]
    if isinstance(fields, str):
        fields = json.loads(fields)
    corrections = row["corrections"]
    if isinstance(corrections, str):
        corrections = json.loads(corrections)
    return ReviewItem(
        review_id=row["review_id"],
        document_id=row["document_id"],
        document_type=DocumentType(row["document_type"]),
        created_at=row["created_at"],
        status=ReviewStatus(row["status"]),
        fields=[FieldForReview.model_validate(item) for item in fields],
        blocking=bool(row["blocking"]),
        resolved_at=row.get("resolved_at"),
        resolved_by=row.get("resolved_by"),
        corrections=corrections or {},
    )
