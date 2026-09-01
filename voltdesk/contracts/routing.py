"""Model-routing contracts.

Owned by: Phase 1 (definition and interface). Phase 4 implements the policy.
A routing decision is recorded, not inferred: the rationale is written down at the
moment of the choice so the audit log can answer "why this model" months later.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from voltdesk.contracts.common import Provider, StrictModel, TaskType


class RoutingStrategy(StrEnum):
    """How the choice was made. Phase 4 may add members, never remove them."""

    STATIC_DEFAULT = "static_default"
    TASK_TABLE = "task_table"
    COST_OPTIMISED = "cost_optimised"
    FALLBACK_AFTER_ERROR = "fallback_after_error"
    FORCED_BY_CALLER = "forced_by_caller"


class ModelChoice(StrictModel):
    """A concrete, callable model identity."""

    provider: Provider
    model_id: str = Field(
        description=(
            "Exact provider model string, no date suffix invented by us. "
            "Anthropic IDs are listed in voltdesk/llm/pricing.py; OpenAI IDs carry a "
            "TODO(verify) there because they were not verified in Phase 1."
        )
    )


class RoutingDecision(StrictModel):
    """The record of one routing choice."""

    task_type: TaskType
    chosen: ModelChoice
    strategy: RoutingStrategy
    rationale: str = Field(
        min_length=1,
        description="One sentence, human-readable. Written for whoever reads the audit log.",
    )
    considered: list[ModelChoice] = Field(
        default_factory=list, description="Candidates that were available but not chosen."
    )
    estimated_input_tokens: int | None = Field(default=None, ge=0)
    fallback_of: ModelChoice | None = Field(
        default=None, description="Set when this decision replaced a failed call."
    )
