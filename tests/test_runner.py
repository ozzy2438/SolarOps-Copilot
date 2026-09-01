"""Resumable golden-set execution. Owned by Phase 4."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from voltdesk.contracts.common import Provider, TaskType
from voltdesk.contracts.evaluation import EvaluationResult, GoldenRecord, RecordResult
from voltdesk.contracts.routing import ModelChoice
from voltdesk.evaluation import metrics
from voltdesk.evaluation.runner import load_golden_set, run
from voltdesk.evaluation.store import PartialEvaluation

MODEL = ModelChoice(provider=Provider.ANTHROPIC, model_id="claude-opus-5")
SHA = "a" * 40


class MemoryStore:
    def __init__(self, partial: PartialEvaluation | None = None) -> None:
        self.partial = partial
        self.checkpoint_sizes: list[int] = []
        self.finished: EvaluationResult | None = None

    def start(self, run_id: str, started_at: datetime, model: ModelChoice, git_sha: str) -> None:
        self.partial = PartialEvaluation(started_at, model, git_sha, [])

    def load(self, run_id: str) -> PartialEvaluation | None:
        return self.partial

    def checkpoint(self, run_id: str, results: list[RecordResult]) -> None:
        assert self.partial is not None
        self.checkpoint_sizes.append(len(results))
        self.partial = PartialEvaluation(
            self.partial.started_at,
            self.partial.model,
            self.partial.git_sha,
            list(results),
        )

    def finish(self, result: EvaluationResult) -> None:
        self.finished = result


def _record(record_id: str) -> GoldenRecord:
    return GoldenRecord(
        record_id=record_id,
        task_type=TaskType.BILL_EXTRACTION,
        input_path=f"data/generated/bills/{record_id}.pdf",
        expected={"nmi": "6305888444"},
        ground_truth_source="generator_seed",
    )


def _result(record: GoldenRecord) -> RecordResult:
    return RecordResult(
        record_id=record.record_id,
        task_type=record.task_type,
        model=MODEL,
        exact_match=True,
        latency_ms=10,
        cost_usd=0.01,
    )


def _summary(results: list[RecordResult]) -> EvaluationResult:
    now = datetime.now(UTC)
    return EvaluationResult(
        run_id="summary",
        started_at=now,
        finished_at=now,
        model=MODEL,
        git_sha="summary",
        record_count=len(results),
        exact_match_rate=1.0,
        field_precision=1.0,
        field_recall=1.0,
        p50_latency_ms=10,
        p95_latency_ms=10,
        total_cost_usd=sum(result.cost_usd for result in results),
        cost_per_document_usd=0.01,
        results=results,
    )


def test_load_golden_set_has_the_binding_split() -> None:
    records = load_golden_set()
    assert len(records) == 150
    assert sum(record.task_type == TaskType.BILL_EXTRACTION for record in records) == 50
    assert sum(record.task_type == TaskType.SITE_ASSESSMENT_EXTRACTION for record in records) == 30
    assert sum(record.task_type == TaskType.EMAIL_EXTRACTION for record in records) == 30
    qa = [record for record in records if record.task_type == TaskType.KNOWLEDGE_QA]
    assert len(qa) == 40
    assert sum(bool(record.expected["should_abstain"]) for record in qa) == 15


def test_run_checkpoints_every_record(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [_record("bill-0001"), _record("bill-0002")]
    store = MemoryStore()
    monkeypatch.setattr(metrics, "summarise", _summary)
    result = run(
        records, MODEL, executor=lambda record, _model: _result(record), store=store, git_sha=SHA
    )
    assert store.checkpoint_sizes == [1, 2]
    assert result.git_sha == SHA
    assert result.record_count == 2
    assert store.finished == result


def test_resume_skips_already_checkpointed_records(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [_record("bill-0001"), _record("bill-0002")]
    partial = PartialEvaluation(datetime.now(UTC), MODEL, SHA, [_result(records[0])])
    store = MemoryStore(partial)
    executed: list[str] = []

    def execute(record: GoldenRecord, _model: ModelChoice) -> RecordResult:
        executed.append(record.record_id)
        return _result(record)

    monkeypatch.setattr(metrics, "summarise", _summary)
    result = run(
        records,
        MODEL,
        resume_run_id="eval-existing",
        executor=execute,
        store=store,
        git_sha=SHA,
    )
    assert executed == ["bill-0002"]
    assert result.run_id == "eval-existing"
    assert store.checkpoint_sizes == [2]
