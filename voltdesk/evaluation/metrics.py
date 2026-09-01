"""Metric computation.

Owned by: Phase 4. Definitions are in docs/EVALUATION.md and are binding - a metric
computed differently from its written definition makes the whole report unreadable.

Note on field-level precision and recall: the denominators differ. Precision is over
fields the model produced a value for; recall is over fields ground truth has a value
for. A model that returns null for everything has undefined precision and zero
recall, and the code must not paper over that with a zero.
"""

from __future__ import annotations

from voltdesk.contracts.evaluation import EvaluationResult, RecordResult


def field_precision(results: list[RecordResult]) -> float:
    raise NotImplementedError(
        "field_precision is implemented in Phase 4 (docs/PHASE_4.md, step 3)"
    )


def field_recall(results: list[RecordResult]) -> float:
    raise NotImplementedError(
        "field_recall is implemented in Phase 4 (docs/PHASE_4.md, step 3)"
    )


def exact_match_rate(results: list[RecordResult]) -> float:
    raise NotImplementedError(
        "exact_match_rate is implemented in Phase 4 (docs/PHASE_4.md, step 3)"
    )


def abstention_precision_recall(results: list[RecordResult]) -> tuple[float, float]:
    raise NotImplementedError(
        "abstention_precision_recall is implemented in Phase 4 (docs/PHASE_4.md, step 3)"
    )


def coverage_accuracy_curve(results: list[RecordResult]) -> list[tuple[float, float, float]]:
    """(confidence threshold, coverage, accuracy) triples.

    This is the curve that answers the only question the business actually has:
    at what confidence can a field be written without a human, and what fraction of
    fields clear that bar?
    """
    raise NotImplementedError(
        "coverage_accuracy_curve is implemented in Phase 4 (docs/PHASE_4.md, step 3)"
    )


def summarise(results: list[RecordResult]) -> EvaluationResult:
    raise NotImplementedError(
        "summarise is implemented in Phase 4 (docs/PHASE_4.md, step 3)"
    )
