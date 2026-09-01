"""Human review queue routes.

Owned by: Phase 1 (route signatures). Phase 2 implements the bodies.

This is an API, not a UI. Building a review interface, or any part of a CRM UI, is
permanently out of scope (docs/SCOPE.md); reviewers work through EspoCRM or curl.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from voltdesk.review.queue import ReviewNotFoundError, ReviewQueue

router = APIRouter(prefix="/review", tags=["review"])


@router.get("")
async def list_pending(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)
) -> dict[str, Any]:
    items = ReviewQueue().list_pending(limit=limit, offset=offset)
    return {"items": [item.model_dump(mode="json") for item in items]}


@router.get("/{review_id}")
async def get_review(review_id: str) -> dict[str, Any]:
    try:
        item = ReviewQueue().get(review_id)
    except ReviewNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "review not found") from exc
    return item.model_dump(mode="json")


@router.post("/{review_id}/resolve")
async def resolve_review(review_id: str, corrections: dict[str, Any]) -> dict[str, Any]:
    """Apply corrections and retain them as ground truth for the golden set."""
    try:
        item = ReviewQueue().resolve(review_id, corrections, resolved_by="api")
    except ReviewNotFoundError as extra:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "review not found") from extra
    return item.model_dump(mode="json")
