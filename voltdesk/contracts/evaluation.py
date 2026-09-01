"""Evaluation contracts: the golden set and the numbers computed from it.

Owned by: Phase 1 (definition). Phase 4 implements the runner.
Metric definitions live in docs/EVALUATION.md; this file is the shape they take
on disk and on the wire.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from voltdesk.contracts.common import StrictModel, TaskType
from voltdesk.contracts.routing import ModelChoice


class GoldenRecord(StrictModel):
    """One evaluation case with human-established ground truth."""

    record_id: str = Field(description="Stable, e.g. 'bill-0042'. Used as the filename stem.")
    task_type: TaskType
    input_path: str = Field(description="Path relative to the repo root of the input artefact.")
    expected: dict[str, Any] = Field(
        description=(
            "Ground truth. For extraction tasks: field_path -> expected value. For QA: "
            "keys 'answer_contains', 'required_citation_chunk_ids', 'should_abstain'."
        )
    )
    ground_truth_source: str = Field(
        description=(
            "How truth was established: 'human_labelled', 'reviewer_correction', or "
            "'generator_seed' for synthetic records where the generator knows the answer."
        )
    )
    notes: str | None = None


class FieldScore(StrictModel):
    """Per-field outcome for one record, the unit precision and recall are computed over."""

    field_path: str
    expected: Any
    actual: Any
    correct: bool
    predicted_present: bool = Field(description="Did the model produce a non-null value?")
    expected_present: bool = Field(description="Does ground truth have a value?")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class RecordResult(StrictModel):
    """What happened when one golden record was run against one model."""

    record_id: str
    task_type: TaskType
    model: ModelChoice
    exact_match: bool = Field(description="Every field correct.")
    field_scores: list[FieldScore] = Field(default_factory=list)
    abstained: bool | None = Field(default=None, description="QA tasks only.")
    citations_correct: bool | None = Field(default=None, description="QA tasks only.")
    latency_ms: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    error: str | None = None


class EvaluationResult(StrictModel):
    """One complete run of the golden set against one model configuration."""

    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    model: ModelChoice
    git_sha: str = Field(description="Commit the run was executed at.")
    record_count: int = Field(ge=0)

    exact_match_rate: float = Field(ge=0.0, le=1.0)
    field_precision: float = Field(ge=0.0, le=1.0)
    field_recall: float = Field(ge=0.0, le=1.0)
    citation_correctness: float | None = Field(default=None, ge=0.0, le=1.0)
    abstention_precision: float | None = Field(default=None, ge=0.0, le=1.0)
    abstention_recall: float | None = Field(default=None, ge=0.0, le=1.0)
    p50_latency_ms: int = Field(ge=0)
    p95_latency_ms: int = Field(ge=0)
    total_cost_usd: float = Field(ge=0.0)
    cost_per_document_usd: float = Field(ge=0.0)

    results: list[RecordResult] = Field(default_factory=list)
