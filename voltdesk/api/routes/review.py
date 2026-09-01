"""Human review queue routes.

Owned by: Phase 1 (route signatures). Phase 2 implements the bodies.

This is an API, not a UI. Building a review interface, or any part of a CRM UI, is
permanently out of scope (docs/SCOPE.md); reviewers work through EspoCRM or curl.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

router = APIRouter(prefix="/review", tags=["review"])

_PHASE_2 = "implemented in Phase 2 - see docs/PHASE_2.md"


@router.get("")
async def list_pending(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)
) -> dict[str, Any]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"list_pending is {_PHASE_2}")


@router.get("/{review_id}")
async def get_review(review_id: str) -> dict[str, Any]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"get_review is {_PHASE_2}")


@router.post("/{review_id}/resolve")
async def resolve_review(review_id: str, corrections: dict[str, Any]) -> dict[str, Any]:
    """Apply corrections, release any held CRM write, retain the correction as
    ground truth for the golden set."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"resolve_review is {_PHASE_2}")
