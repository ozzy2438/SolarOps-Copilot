"""Operational routes: evaluation runs and the incident log.

Owned by: Phase 1 (route signatures). Phase 4 implements the bodies.

No authentication. Multi-tenancy, user management and RBAC are permanently out of
scope (docs/SCOPE.md); this service is deployed behind the company's own network
boundary. That is a real constraint on where it may be deployed, and it is stated
in docs/ARCHITECTURE.md under the trust boundary rather than left implicit.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/admin", tags=["admin"])

_PHASE_4 = "implemented in Phase 4 - see docs/PHASE_4.md"


@router.post("/evaluations")
async def start_evaluation(model_id: str) -> dict[str, Any]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"start_evaluation is {_PHASE_4}")


@router.get("/evaluations/{run_id}")
async def get_evaluation(run_id: str) -> dict[str, Any]:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"get_evaluation is {_PHASE_4}")


@router.get("/incidents")
async def list_incidents() -> dict[str, Any]:
    """The written incident log. Phase 4 owns keeping it honest."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"list_incidents is {_PHASE_4}")
