"""Daily document processing and reduced golden-set regression check.

The scheduled RQ job is intentionally small: it processes documents received today,
runs two golden records per task, persists the evaluation through the normal runner,
and opens an incident when either headline quality measure drops by more than five
percentage points from the latest comparable reduced run.
"""

from __future__ import annotations

import argparse
import uuid
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from sqlalchemy import text

from voltdesk.contracts.evaluation import EvaluationResult
from voltdesk.contracts.routing import ModelChoice
from voltdesk.db.session import get_engine
from voltdesk.evaluation.runner import load_golden_set, run, select_pilot
from voltdesk.jobs import process_document
from voltdesk.llm.pricing import DEFAULT_MODEL_ID, get_price

REDUCED_RECORDS_PER_TASK = 2
REGRESSION_TOLERANCE = 0.05

_TODAYS_RECEIVED_DOCUMENTS = text(
    """
    SELECT id FROM app.documents
    WHERE status = 'received'
      AND received_at >= date_trunc('day', NOW())
    ORDER BY received_at, id
    """
)
_LATEST_COMPARABLE = text(
    """
    SELECT run_id, exact_match_rate, field_recall
    FROM app.evaluation_runs
    WHERE model_id = :model_id
      AND record_count = :record_count
      AND finished_at IS NOT NULL
    ORDER BY finished_at DESC
    LIMIT 1
    """
)
_INSERT_INCIDENT = text(
    """
    INSERT INTO app.incidents
        (id, severity, title, summary, root_cause, remediation, related_call_ids)
    VALUES
        (:id, 'medium', :title, :summary, :root_cause, :remediation,
         ARRAY[]::text[])
    """
)


def _choice(model_id: str) -> ModelChoice:
    price = get_price(model_id)
    return ModelChoice(provider=price.provider, model_id=price.model_id)


def _received_document_ids() -> list[str]:
    with get_engine().connect() as connection:
        return [str(value) for value in connection.execute(_TODAYS_RECEIVED_DOCUMENTS).scalars()]


def _latest_comparable(model_id: str, record_count: int) -> dict[str, Any] | None:
    with get_engine().connect() as connection:
        row = connection.execute(
            _LATEST_COMPARABLE,
            {"model_id": model_id, "record_count": record_count},
        ).mappings().one_or_none()
    return dict(row) if row is not None else None


def _regressions(
    baseline: dict[str, Any] | None,
    result: EvaluationResult,
) -> list[str]:
    if baseline is None:
        return []
    findings: list[str] = []
    for column, current in (
        ("exact_match_rate", result.exact_match_rate),
        ("field_recall", result.field_recall),
    ):
        previous = baseline.get(column)
        if (
            previous is not None
            and float(previous) - current > REGRESSION_TOLERANCE + 1e-12
        ):
            findings.append(f"{column}: {float(previous):.4f} -> {current:.4f}")
    return findings


def _open_regression_incident(
    model_id: str,
    baseline_run_id: str,
    current_run_id: str,
    findings: list[str],
) -> str:
    incident_id = f"incident-{uuid.uuid4()}"
    with get_engine().begin() as connection:
        connection.execute(
            _INSERT_INCIDENT,
            {
                "id": incident_id,
                "title": "Reduced golden-set regression",
                "summary": (
                    f"Daily run {current_run_id} regressed versus {baseline_run_id}: "
                    + "; ".join(findings)
                ),
                "root_cause": "Not yet determined; opened automatically by the daily batch.",
                "remediation": (
                    f"Review {model_id} audit calls and record-level results before promotion."
                ),
            },
        )
    return incident_id


def run_daily_batch(
    *,
    model_id: str = DEFAULT_MODEL_ID,
    records_per_task: int = REDUCED_RECORDS_PER_TASK,
) -> dict[str, object]:
    """Process today's queue, run the reduced set, and record regressions."""
    document_ids = _received_document_ids()
    for document_id in document_ids:
        process_document(document_id)

    records = select_pilot(load_golden_set(), records_per_task)
    baseline = _latest_comparable(model_id, len(records))
    result = run(records, _choice(model_id))
    findings = _regressions(baseline, result)
    incident_id = None
    if findings and baseline is not None:
        incident_id = _open_regression_incident(
            model_id,
            str(baseline["run_id"]),
            result.run_id,
            findings,
        )
    return {
        "documents_processed": len(document_ids),
        "evaluation_run_id": result.run_id,
        "model_id": model_id,
        "record_count": result.record_count,
        "regressions": findings,
        "incident_id": incident_id,
    }


def schedule_next_run(*, delay: timedelta = timedelta(days=1)) -> str:
    """Put one future daily run in RQ's scheduled registry."""
    from redis import Redis
    from rq import Queue

    from voltdesk.config import get_settings

    queue = Queue("voltdesk", connection=Redis.from_url(get_settings().redis_url))
    job = queue.enqueue_in(delay, scheduled_run, job_timeout="2h")
    return str(job.id)


def scheduled_run() -> dict[str, object]:
    """RQ entry point that keeps the once-per-day chain alive after every attempt."""
    try:
        return run_daily_batch()
    finally:
        schedule_next_run()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Run the daily batch now")
    mode.add_argument("--schedule", action="store_true", help="Schedule the first run in 24h")
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--records-per-task", type=int, default=REDUCED_RECORDS_PER_TASK)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.records_per_task <= 0:
        raise SystemExit("--records-per-task must be positive")
    if args.once:
        import json

        print(
            json.dumps(
                run_daily_batch(
                    model_id=args.model,
                    records_per_task=args.records_per_task,
                ),
                sort_keys=True,
            )
        )
    else:
        print(schedule_next_run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
