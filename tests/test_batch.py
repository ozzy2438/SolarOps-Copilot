"""Daily batch scheduling and regression behaviour."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from voltdesk import batch
from voltdesk.contracts.common import Provider
from voltdesk.contracts.evaluation import EvaluationResult
from voltdesk.contracts.routing import ModelChoice


def _evaluation(*, exact: float = 0.75, recall: float = 0.8) -> EvaluationResult:
    now = datetime.now(UTC)
    return EvaluationResult(
        run_id="eval-current",
        started_at=now,
        finished_at=now,
        model=ModelChoice(provider=Provider.OPENAI, model_id="gpt-4o-mini"),
        git_sha="a" * 40,
        record_count=8,
        exact_match_rate=exact,
        field_precision=0.9,
        field_recall=recall,
        p50_latency_ms=10,
        p95_latency_ms=20,
        total_cost_usd=0.01,
        cost_per_document_usd=0.00125,
    )


def test_daily_batch_processes_documents_and_writes_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processed: list[str] = []
    monkeypatch.setattr(batch, "_received_document_ids", lambda: ["doc-1", "doc-2"])
    monkeypatch.setattr(batch, "process_document", processed.append)
    monkeypatch.setattr(batch, "load_golden_set", lambda: list(range(20)))
    monkeypatch.setattr(batch, "select_pilot", lambda records, per_task: records[:8])
    monkeypatch.setattr(batch, "_latest_comparable", lambda _model, _count: None)
    monkeypatch.setattr(batch, "run", lambda _records, _model: _evaluation())

    result = batch.run_daily_batch()

    assert processed == ["doc-1", "doc-2"]
    assert result["documents_processed"] == 2
    assert result["evaluation_run_id"] == "eval-current"
    assert result["record_count"] == 8
    assert result["incident_id"] is None


def test_daily_batch_opens_incident_only_for_material_regression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[list[str]] = []
    monkeypatch.setattr(batch, "_received_document_ids", lambda: [])
    monkeypatch.setattr(batch, "load_golden_set", lambda: list(range(8)))
    monkeypatch.setattr(batch, "select_pilot", lambda records, _per_task: records)
    monkeypatch.setattr(
        batch,
        "_latest_comparable",
        lambda _model, _count: {
            "run_id": "eval-baseline",
            "exact_match_rate": 0.9,
            "field_recall": 0.82,
        },
    )
    monkeypatch.setattr(batch, "run", lambda _records, _model: _evaluation())

    def open_incident(
        _model: str, _baseline: str, _current: str, findings: list[str]
    ) -> str:
        opened.append(findings)
        return "incident-1"

    monkeypatch.setattr(batch, "_open_regression_incident", open_incident)

    result = batch.run_daily_batch()

    assert result["incident_id"] == "incident-1"
    assert opened == [["exact_match_rate: 0.9000 -> 0.7500"]]


def test_regression_tolerance_is_strictly_more_than_five_points() -> None:
    baseline = {"run_id": "prior", "exact_match_rate": 0.8, "field_recall": 0.85}

    assert batch._regressions(baseline, _evaluation(exact=0.75, recall=0.8)) == []
    assert batch._regressions(baseline, _evaluation(exact=0.74, recall=0.79)) == [
        "exact_match_rate: 0.8000 -> 0.7400",
        "field_recall: 0.8500 -> 0.7900",
    ]
