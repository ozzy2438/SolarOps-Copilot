"""The audit record: one row per model call, no exceptions.

Owned by: Phase 1. Fully implemented in Phase 1 because every later phase writes
to it and none of them may change its shape.

The field list here is the contract behind migrations/0004_audit.sql. If you add a
field, add a migration in the same change - a contract field with no column is a
silent data loss bug.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from voltdesk.contracts.common import CallOutcome, StrictModel, TaskType
from voltdesk.contracts.routing import RoutingDecision


class TokenUsage(StrictModel):
    """Token counts as reported by the provider, never estimated by us.

    Anthropic reports these on `response.usage`; OpenAI reports `prompt_tokens` /
    `completion_tokens`. The provider adapters normalise into this shape.
    """

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_read_input_tokens: int = Field(
        default=0, ge=0, description="Anthropic prompt caching; 0 when not applicable."
    )
    cache_creation_input_tokens: int = Field(default=0, ge=0)


class AuditRecord(StrictModel):
    """Everything that must be knowable about a single model call after the fact."""

    call_id: str = Field(description="UUID4, generated before the call is made.")
    occurred_at: datetime
    task_type: TaskType
    routing: RoutingDecision

    prompt_version_hash: str = Field(
        min_length=64,
        max_length=64,
        description=(
            "SHA-256 of the rendered prompt template (not the filled-in prompt). "
            "Makes 'which prompt produced this' answerable after a prompt edit."
        ),
    )
    usage: TokenUsage
    cost_usd: float = Field(
        ge=0.0,
        description="Computed from voltdesk/llm/pricing.py at call time, not at read time.",
    )
    latency_ms: int = Field(ge=0)
    outcome: CallOutcome
    error_message: str | None = None
    retry_count: int = Field(default=0, ge=0)

    redaction_applied: bool = Field(
        description=(
            "True when the PII redactor modified the payload before it left the "
            "trust boundary. False here with PII in the payload is an incident."
        )
    )
    redacted_entity_counts: dict[str, int] = Field(
        default_factory=dict, description="Entity type -> count redacted, e.g. {'EMAIL': 2}."
    )

    document_id: str | None = Field(default=None, description="Set for extraction tasks.")
    query_id: str | None = Field(default=None, description="Set for Q&A tasks.")
