"""Operational metrics, read from the audit log.

Owned by: Phase 1 (the endpoint and the queries). Phase 4 adds the rendered page.

Everything here is computed from app.model_calls. There is no separate metrics
store to drift out of sync with the audit trail - the audit trail is the metrics
store.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import text

from voltdesk.db.session import get_engine

router = APIRouter(prefix="/metrics", tags=["metrics"])

_SUMMARY = text(
    """
    SELECT
        task_type,
        model_id,
        COUNT(*)                                        AS calls,
        SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) AS successes,
        SUM(cost_usd)                                   AS cost_usd,
        AVG(latency_ms)                                 AS mean_latency_ms,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
        SUM(input_tokens)                               AS input_tokens,
        SUM(output_tokens)                              AS output_tokens
    FROM app.model_calls
    WHERE occurred_at >= NOW() - CAST(:window AS interval)
    GROUP BY task_type, model_id
    ORDER BY calls DESC
    """
)

_REDACTION = text(
    """
    SELECT
        COUNT(*)                                                  AS calls,
        SUM(CASE WHEN redaction_applied THEN 1 ELSE 0 END)        AS redacted_calls
    FROM app.model_calls
    WHERE occurred_at >= NOW() - CAST(:window AS interval)
    """
)


@router.get("")
def metrics(hours: int = Query(default=24, ge=1, le=24 * 30)) -> dict[str, Any]:
    """Per task type and model, over a trailing window."""
    window = f"{hours} hours"
    with get_engine().connect() as connection:
        rows = connection.execute(_SUMMARY, {"window": window}).mappings().all()
        redaction = connection.execute(_REDACTION, {"window": window}).mappings().one()

    return {
        "window_hours": hours,
        "by_task": [dict(row) for row in rows],
        "totals": {
            "calls": sum(row["calls"] for row in rows),
            "cost_usd": float(sum(row["cost_usd"] or 0 for row in rows)),
        },
        "redaction": {
            "calls": redaction["calls"],
            "redacted_calls": redaction["redacted_calls"],
        },
    }
