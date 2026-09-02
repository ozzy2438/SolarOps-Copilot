"""Operational routes: evaluation runs and the incident log.

Owned by: Phase 1 (route signatures). Phase 4 implements the bodies.

No authentication. Multi-tenancy, user management and RBAC are permanently out of
scope (docs/SCOPE.md); this service is deployed behind the company's own network
boundary. That is a real constraint on where it may be deployed, and it is stated
in docs/ARCHITECTURE.md under the trust boundary rather than left implicit.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from voltdesk.db.session import get_engine
from voltdesk.evaluation.runner import run_model
from voltdesk.llm.pricing import UnknownModelError, UnverifiedPriceError, assert_verified

router = APIRouter(prefix="/admin", tags=["admin"])

_EVALUATION = text(
    """
    SELECT run_id, started_at, finished_at, provider, model_id, git_sha,
           record_count, exact_match_rate, field_precision, field_recall,
           citation_correctness, abstention_precision, abstention_recall,
           p50_latency_ms, p95_latency_ms, total_cost_usd
    FROM app.evaluation_runs WHERE run_id = :run_id
    """
)
_INCIDENTS = text(
    """
    SELECT id, opened_at, resolved_at, severity, title, summary, root_cause,
           remediation, related_call_ids
    FROM app.incidents ORDER BY opened_at DESC
    """
)


def _jsonable(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: float(value) if isinstance(value, Decimal) else value for key, value in row.items()
    }


def _enqueue_evaluation(model_id: str) -> str:
    from redis import Redis
    from rq import Queue

    from voltdesk.config import get_settings

    queue = Queue("voltdesk", connection=Redis.from_url(get_settings().redis_url))
    job = queue.enqueue(run_model, model_id, job_timeout="2h")
    return str(job.id)


def _read_evaluation(run_id: str) -> dict[str, Any] | None:
    with get_engine().connect() as connection:
        row = connection.execute(_EVALUATION, {"run_id": run_id}).mappings().one_or_none()
    return _jsonable(dict(row)) if row is not None else None


def _read_incidents() -> list[dict[str, Any]]:
    with get_engine().connect() as connection:
        return [_jsonable(dict(row)) for row in connection.execute(_INCIDENTS).mappings()]


@router.post("/evaluations", status_code=status.HTTP_202_ACCEPTED)
async def start_evaluation(model_id: str) -> dict[str, Any]:
    try:
        assert_verified(model_id)
    except (UnknownModelError, UnverifiedPriceError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"job_id": _enqueue_evaluation(model_id), "model_id": model_id, "status": "queued"}


@router.get("/evaluations/{run_id}")
async def get_evaluation(run_id: str) -> dict[str, Any]:
    result = _read_evaluation(run_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "evaluation run not found")
    return result


@router.get("/incidents")
async def list_incidents() -> dict[str, Any]:
    """The written incident log. Phase 4 owns keeping it honest."""
    return {"incidents": _read_incidents()}
