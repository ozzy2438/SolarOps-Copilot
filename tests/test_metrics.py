"""Metric denominators and aggregation. Owned by Phase 4."""

from __future__ import annotations

import pytest

from voltdesk.contracts.common import Provider, TaskType
from voltdesk.contracts.evaluation import FieldScore, RecordResult
from voltdesk.contracts.routing import ModelChoice
from voltdesk.evaluation.metrics import (
    abstention_precision_recall,
    citation_correctness,
    coverage_accuracy_curve,
    exact_match_rate,
    field_precision,
    field_recall,
    summarise,
)

MODEL = ModelChoice(provider=Provider.ANTHROPIC, model_id="claude-opus-5")


def _field(
    *,
    correct: bool,
    predicted: bool,
    expected: bool,
    confidence: float | None = None,
) -> FieldScore:
    return FieldScore(
        field_path="value",
        expected="expected" if expected else None,
        actual="actual" if predicted else None,
        correct=correct,
        predicted_present=predicted,
        expected_present=expected,
        confidence=confidence,
    )


def _extraction(record_id: str, scores: list[FieldScore], *, latency: int = 10) -> RecordResult:
    return RecordResult(
        record_id=record_id,
        task_type=TaskType.BILL_EXTRACTION,
        model=MODEL,
        exact_match=all(score.correct for score in scores),
        field_scores=scores,
        latency_ms=latency,
        cost_usd=0.01,
    )


def _qa(
    record_id: str,
    *,
    should_abstain: bool,
    abstained: bool,
    citations_correct: bool | None,
) -> RecordResult:
    return RecordResult(
        record_id=record_id,
        task_type=TaskType.KNOWLEDGE_QA,
        model=MODEL,
        exact_match=should_abstain == abstained,
        field_scores=[
            FieldScore(
                field_path="should_abstain",
                expected=should_abstain,
                actual=abstained,
                correct=should_abstain == abstained,
                predicted_present=True,
                expected_present=True,
                confidence=0.5,
            )
        ],
        abstained=abstained,
        citations_correct=citations_correct,
        latency_ms=20,
        cost_usd=0.02,
    )


def test_precision_denominator_all_null_is_undefined() -> None:
    results = [_extraction("r1", [_field(correct=False, predicted=False, expected=True)])]
    assert field_precision(results) is None
    assert field_recall(results) == 0.0


def test_precision_and_recall_use_different_denominators() -> None:
    results = [
        _extraction(
            "r1",
            [
                _field(correct=True, predicted=True, expected=True),
                _field(correct=False, predicted=True, expected=False),
                _field(correct=False, predicted=False, expected=True),
            ],
        )
    ]
    assert field_precision(results) == 0.5
    assert field_recall(results) == 0.5


def test_exact_match_is_per_record() -> None:
    results = [
        _extraction("r1", [_field(correct=True, predicted=True, expected=True)]),
        _extraction("r2", [_field(correct=False, predicted=True, expected=True)]),
    ]
    assert exact_match_rate(results) == 0.5


def test_abstention_precision_and_recall_use_labelled_denominators() -> None:
    results = [
        _qa("qa-1", should_abstain=True, abstained=True, citations_correct=None),
        _qa("qa-2", should_abstain=True, abstained=False, citations_correct=False),
        _qa("qa-3", should_abstain=False, abstained=True, citations_correct=None),
        _qa("qa-4", should_abstain=False, abstained=False, citations_correct=True),
    ]
    assert abstention_precision_recall(results) == (0.5, 0.5)


def test_citation_correctness_excludes_abstentions() -> None:
    results = [
        _qa("qa-1", should_abstain=True, abstained=True, citations_correct=None),
        _qa("qa-2", should_abstain=False, abstained=False, citations_correct=True),
        _qa("qa-3", should_abstain=False, abstained=False, citations_correct=False),
    ]
    assert citation_correctness(results) == 0.5


def test_coverage_accuracy_curve_uses_confident_predictions() -> None:
    results = [
        _extraction(
            "r1",
            [
                _field(correct=True, predicted=True, expected=True, confidence=0.9),
                _field(correct=False, predicted=True, expected=True, confidence=0.4),
                _field(correct=False, predicted=False, expected=True, confidence=0.0),
            ],
        )
    ]
    curve = {
        threshold: (coverage, accuracy)
        for threshold, coverage, accuracy in coverage_accuracy_curve(results)
    }
    assert curve[0.0] == (1.0, 0.5)
    assert curve[0.5] == (0.5, 1.0)
    assert curve[0.95] == (0.0, None)


def test_summarise_reports_nearest_rank_p95_and_cost() -> None:
    results = [
        _extraction(
            f"r{index}",
            [_field(correct=True, predicted=True, expected=True, confidence=0.9)],
            latency=index,
        )
        for index in range(1, 21)
    ]
    summary = summarise(results)
    assert summary.p50_latency_ms == 10
    assert summary.p95_latency_ms == 19
    assert summary.total_cost_usd == pytest.approx(0.20)
    assert summary.cost_per_document_usd == pytest.approx(0.01)
