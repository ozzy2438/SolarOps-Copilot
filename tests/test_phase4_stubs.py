"""Phase 4's stubs fail loudly and name their phase. Owned by Phase 1."""

from __future__ import annotations

import pytest

from voltdesk.evaluation.metrics import (
    abstention_precision_recall,
    coverage_accuracy_curve,
    exact_match_rate,
    field_precision,
    field_recall,
    summarise,
)
from voltdesk.evaluation.runner import load_golden_set, run, run_benchmark

pytestmark = pytest.mark.phase4


def test_runner_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 4"):
        load_golden_set()
    with pytest.raises(NotImplementedError, match="Phase 4"):
        run([], None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError, match="Phase 4"):
        run_benchmark([])


@pytest.mark.parametrize(
    "fn",
    [
        field_precision,
        field_recall,
        exact_match_rate,
        abstention_precision_recall,
        coverage_accuracy_curve,
        summarise,
    ],
)
def test_metrics_are_not_implemented(fn: object) -> None:
    with pytest.raises(NotImplementedError, match="Phase 4"):
        fn([])  # type: ignore[operator]
