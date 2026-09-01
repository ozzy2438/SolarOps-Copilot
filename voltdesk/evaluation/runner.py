"""Golden set execution.

Owned by: Phase 4. See docs/PHASE_4.md.

The runner is what turns this repository from a demo into evidence. It must be
re-runnable, record the git SHA it ran at, and write results that can be compared
across models and across days.
"""

from __future__ import annotations

from voltdesk.contracts.evaluation import EvaluationResult, GoldenRecord
from voltdesk.contracts.routing import ModelChoice


def load_golden_set(path: str = "data/golden/records") -> list[GoldenRecord]:
    raise NotImplementedError(
        "load_golden_set is implemented in Phase 4 (docs/PHASE_4.md, step 2)"
    )


def run(records: list[GoldenRecord], model: ModelChoice) -> EvaluationResult:
    raise NotImplementedError("run is implemented in Phase 4 (docs/PHASE_4.md, step 2)")


def run_benchmark(models: list[ModelChoice]) -> list[EvaluationResult]:
    """The Claude vs GPT comparison. Must call pricing.assert_verified before
    publishing any cost figure - see voltdesk/llm/pricing.py."""
    raise NotImplementedError(
        "run_benchmark is implemented in Phase 4 (docs/PHASE_4.md, step 4)"
    )
