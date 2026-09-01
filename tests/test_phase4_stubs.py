"""Phase 4 stub locations stay executable as their implementations land."""

from __future__ import annotations

from voltdesk.evaluation.metrics import (
    abstention_precision_recall,
    coverage_accuracy_curve,
    exact_match_rate,
    field_precision,
    field_recall,
    summarise,
)
from voltdesk.evaluation.runner import load_golden_set


def test_runner_stub_is_replaced() -> None:
    assert len(load_golden_set()) == 150


def test_metric_stubs_are_replaced() -> None:
    assert field_precision([]) is None
    assert field_recall([]) is None
    assert exact_match_rate([]) is None
    assert abstention_precision_recall([]) == (None, None)
    assert len(coverage_accuracy_curve([])) == 21


def test_summarise_rejects_an_empty_run() -> None:
    try:
        summarise([])
    except ValueError as exc:
        assert "empty" in str(exc)
    else:  # pragma: no cover - explicit failure message for the retained stub test
        raise AssertionError("summarise accepted an empty run")
