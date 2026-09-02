"""Server-rendered operational metrics page backed by the audit tables."""

from __future__ import annotations

from decimal import Decimal
from html import escape
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from voltdesk.db.session import get_engine

router = APIRouter(prefix="/metrics", tags=["metrics"])

_CALL_TOTALS = text(
    """
    SELECT COUNT(*) AS calls,
           COALESCE(SUM(cost_usd), 0) AS cost_usd,
           COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms), 0)
               AS p95_latency_ms,
           COALESCE(SUM(CASE WHEN redaction_applied THEN 1 ELSE 0 END), 0)
               AS redacted_calls
    FROM app.model_calls
    WHERE occurred_at >= NOW() - INTERVAL '24 hours'
    """
)
_OUTCOMES = text(
    """
    SELECT outcome, COUNT(*) AS calls
    FROM app.model_calls
    WHERE occurred_at >= NOW() - INTERVAL '24 hours'
    GROUP BY outcome ORDER BY outcome
    """
)
_LATEST_EVALUATIONS = text(
    """
    SELECT e.run_id, e.model_id, e.record_count, e.exact_match_rate,
           e.field_precision, e.field_recall, e.p95_latency_ms, e.total_cost_usd,
           e.finished_at,
           (
               SELECT COUNT(*) FILTER (
                          WHERE item.value->>'task_type' = 'knowledge_qa'
                            AND (item.value->>'abstained')::boolean
                      )::float
                      / NULLIF(COUNT(*) FILTER (
                          WHERE item.value->>'task_type' = 'knowledge_qa'
                      ), 0)
               FROM jsonb_array_elements(e.results) AS item(value)
           ) AS abstention_rate
    FROM app.evaluation_runs AS e
    WHERE e.finished_at IS NOT NULL
    ORDER BY e.finished_at DESC
    LIMIT 5
    """
)
_REVIEW_DEPTH = text(
    "SELECT COUNT(*) AS depth FROM app.review_queue WHERE status = 'pending_review'"
)


def _number(value: object) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return value
    raise TypeError(f"unexpected numeric value: {type(value).__name__}")


def _read_snapshot() -> dict[str, Any]:
    with get_engine().connect() as connection:
        totals = dict(connection.execute(_CALL_TOTALS).mappings().one())
        outcomes = [dict(row) for row in connection.execute(_OUTCOMES).mappings()]
        evaluations = [
            dict(row) for row in connection.execute(_LATEST_EVALUATIONS).mappings()
        ]
        review_depth = connection.execute(_REVIEW_DEPTH).scalar_one()
    calls = int(totals["calls"])
    redacted = int(totals["redacted_calls"])
    return {
        "calls": calls,
        "cost_usd": _number(totals["cost_usd"]),
        "p95_latency_ms": _number(totals["p95_latency_ms"]),
        "redaction_coverage": redacted / calls if calls else None,
        "review_queue_depth": int(review_depth),
        "outcomes": outcomes,
        "evaluations": evaluations,
    }


def _fmt(value: object, *, percent: bool = False) -> str:
    if value is None:
        return "undefined"
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        return f"{value * 100:.1f}%" if percent else f"{value:.6f}"
    return escape(str(value))


def _render(snapshot: dict[str, Any]) -> str:
    outcome_rows = "".join(
        "<tr><td>" + escape(str(row["outcome"])) + "</td><td>"
        + escape(str(row["calls"])) + "</td></tr>"
        for row in snapshot["outcomes"]
    ) or "<tr><td colspan='2'>No calls in this window</td></tr>"
    evaluation_rows = "".join(
        "<tr>"
        f"<td>{escape(str(row['model_id']))}</td>"
        f"<td>{escape(str(row['record_count']))}</td>"
        f"<td>{_fmt(row['exact_match_rate'], percent=True)}</td>"
        f"<td>{_fmt(row['abstention_rate'], percent=True)}</td>"
        f"<td>{_fmt(row['p95_latency_ms'])}</td>"
        f"<td>${_fmt(row['total_cost_usd'])}</td>"
        "</tr>"
        for row in snapshot["evaluations"]
    ) or "<tr><td colspan='6'>No completed evaluations</td></tr>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VoltDesk operational metrics</title>
  <style>
    body {{ font: 16px system-ui, sans-serif; margin: 2rem; color: #16231c; }}
    .cards {{ display: flex; flex-wrap: wrap; gap: 1rem; }}
    .card {{ border: 1px solid #c7d5cc; border-radius: .5rem; padding: 1rem; min-width: 12rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; }}
    th, td {{ border-bottom: 1px solid #dce5df; padding: .55rem; text-align: left; }}
  </style>
</head>
<body>
  <h1>VoltDesk operational metrics</h1>
  <p>Audit window: trailing 24 hours. Evaluation rows are the five latest completed runs.</p>
  <section class="cards">
    <div class="card"><strong>Calls</strong><br>{_fmt(snapshot['calls'])}</div>
    <div class="card"><strong>Cost (USD)</strong><br>${_fmt(snapshot['cost_usd'])}</div>
    <div class="card"><strong>p95 latency (ms)</strong><br>{_fmt(snapshot['p95_latency_ms'])}</div>
    <div class="card"><strong>Redaction coverage</strong><br>
      {_fmt(snapshot['redaction_coverage'], percent=True)}</div>
    <div class="card"><strong>Review queue depth</strong><br>
      {_fmt(snapshot['review_queue_depth'])}</div>
  </section>
  <h2>Outcome mix</h2>
  <table><thead><tr><th>Outcome</th><th>Calls</th></tr></thead><tbody>{outcome_rows}</tbody></table>
  <h2>Latest evaluations</h2>
  <table>
    <thead><tr><th>Model</th><th>Records</th><th>Exact match</th>
      <th>Abstention rate</th><th>p95 (ms)</th><th>Cost</th></tr></thead>
    <tbody>{evaluation_rows}</tbody>
  </table>
</body>
</html>"""


@router.get("/page", response_class=HTMLResponse)
def metrics_page() -> HTMLResponse:
    """Human-readable view over the same audit tables as the JSON endpoint."""
    return HTMLResponse(_render(_read_snapshot()))
