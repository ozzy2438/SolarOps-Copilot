"""Binding Phase 4 metric definitions from docs/EVALUATION.md."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from voltdesk.contracts.common import TaskType
from voltdesk.contracts.evaluation import EvaluationResult, FieldScore, RecordResult


class UndefinedMetricError(ValueError):
    """Raised when a required published metric has no valid denominator."""


def _extraction_fields(results: list[RecordResult]) -> list[FieldScore]:
    return [
        score
        for result in results
        if result.task_type != TaskType.KNOWLEDGE_QA
        for score in result.field_scores
    ]


def field_precision(results: list[RecordResult]) -> float | None:
    """Correct predicted-present fields divided by predicted-present fields."""
    predicted = [score for score in _extraction_fields(results) if score.predicted_present]
    if not predicted:
        return None
    return sum(score.correct for score in predicted) / len(predicted)


def field_recall(results: list[RecordResult]) -> float | None:
    """Correct expected-present fields divided by expected-present fields."""
    expected = [score for score in _extraction_fields(results) if score.expected_present]
    if not expected:
        return None
    return sum(score.correct for score in expected) / len(expected)


def exact_match_rate(results: list[RecordResult]) -> float | None:
    if not results:
        return None
    return sum(result.exact_match for result in results) / len(results)


def abstention_precision_recall(
    results: list[RecordResult],
) -> tuple[float | None, float | None]:
    """Return abstention precision and recall using their distinct denominators."""
    qa = [result for result in results if result.task_type == TaskType.KNOWLEDGE_QA]
    labelled = [
        (result, score)
        for result in qa
        for score in result.field_scores
        if score.field_path == "should_abstain"
    ]
    abstained = [(result, score) for result, score in labelled if result.abstained is True]
    should_abstain = [(result, score) for result, score in labelled if score.expected is True]
    correctly_abstained = sum(
        result.abstained is True and score.expected is True for result, score in labelled
    )
    precision = correctly_abstained / len(abstained) if abstained else None
    recall = correctly_abstained / len(should_abstain) if should_abstain else None
    return precision, recall


def coverage_accuracy_curve(
    results: list[RecordResult],
) -> list[tuple[float, float, float | None]]:
    """Return (threshold, coverage, accuracy) for thresholds 0.00 through 1.00."""
    fields = [
        score
        for score in _extraction_fields(results)
        if score.predicted_present and score.confidence is not None
    ]
    curve: list[tuple[float, float, float | None]] = []
    for step in range(21):
        threshold = step / 20
        selected = [
            score
            for score in fields
            if score.confidence is not None and score.confidence >= threshold
        ]
        coverage = len(selected) / len(fields) if fields else 0.0
        accuracy = sum(score.correct for score in selected) / len(selected) if selected else None
        curve.append((threshold, coverage, accuracy))
    return curve


def citation_correctness(results: list[RecordResult]) -> float | None:
    """Correct citations divided by answered QA records, never abstentions."""
    answered = [
        result
        for result in results
        if result.task_type == TaskType.KNOWLEDGE_QA and result.abstained is False
    ]
    if not answered:
        return None
    return sum(result.citations_correct is True for result in answered) / len(answered)


def _percentile(values: list[int], probability: float) -> int:
    ordered = sorted(values)
    index = max(0, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def summarise(results: list[RecordResult]) -> EvaluationResult:
    """Aggregate one model's records, refusing undefined required metrics."""
    if not results:
        raise ValueError("cannot summarise an empty evaluation run")
    models = {result.model.model_dump_json() for result in results}
    if len(models) != 1:
        raise ValueError("one EvaluationResult cannot mix models")
    precision = field_precision(results)
    recall = field_recall(results)
    exact = exact_match_rate(results)
    if precision is None:
        raise UndefinedMetricError("field precision is undefined: no field was predicted present")
    if recall is None:
        raise UndefinedMetricError("field recall is undefined: no ground-truth field is present")
    assert exact is not None
    abstention_precision, abstention_recall = abstention_precision_recall(results)
    latencies = [result.latency_ms for result in results]
    total_cost = sum(result.cost_usd for result in results)
    now = datetime.now(UTC)
    return EvaluationResult(
        run_id="summary-not-publishable",
        started_at=now,
        finished_at=now,
        model=results[0].model,
        git_sha="summary-not-publishable",
        record_count=len(results),
        exact_match_rate=exact,
        field_precision=precision,
        field_recall=recall,
        citation_correctness=citation_correctness(results),
        abstention_precision=abstention_precision,
        abstention_recall=abstention_recall,
        p50_latency_ms=_percentile(latencies, 0.50),
        p95_latency_ms=_percentile(latencies, 0.95),
        total_cost_usd=total_cost,
        cost_per_document_usd=total_cost / len(results),
        results=results,
    )
