"""Human review queue contracts.

Owned by: Phase 1 (definition). Phase 2 implements the queue.
The queue exists because of the confidence-band policy in docs/GUARDRAILS.md:
some fields must never reach the CRM without a person having looked at them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from voltdesk.contracts.common import DocumentType, ReviewStatus, StrictModel


class FieldForReview(StrictModel):
    """One field a human must confirm, correct, or reject."""

    field_path: str = Field(
        description="Dotted path into the extraction contract, e.g. 'nmi' or 'components.0.label'."
    )
    proposed_value: Any = Field(description="What the model extracted. May be null.")
    confidence: float = Field(ge=0.0, le=1.0)
    source_quote: str | None = None
    source_page: int | None = Field(default=None, ge=1)
    reason: str = Field(
        min_length=1,
        description="Why this needs a human, in the reviewer's language, not ours.",
    )


class ReviewItem(StrictModel):
    """One document awaiting review. Not one field - a reviewer works a document at a time."""

    review_id: str
    document_id: str
    document_type: DocumentType
    created_at: datetime
    status: ReviewStatus
    fields: list[FieldForReview] = Field(min_length=1)
    blocking: bool = Field(
        description=(
            "True when nothing may be written to the CRM until this is resolved - for "
            "example a bill whose NMI is uncertain. False when the confident fields were "
            "already written and only the uncertain ones are held back."
        )
    )
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    corrections: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "field_path -> corrected value, filled by the reviewer. Phase 4 mines this "
            "as ground truth for the golden set; see docs/EVALUATION.md."
        ),
    )
