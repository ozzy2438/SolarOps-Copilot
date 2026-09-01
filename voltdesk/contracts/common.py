"""Shared primitives for every VoltDesk contract.

Owned by: Phase 1. Later phases may add members to the enums and fields to the
models, but may never rename or remove one. See contracts/README.md.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class StrictModel(BaseModel):
    """Base for every contract.

    Forbidding extra keys is deliberate: an LLM that invents a field must fail
    validation loudly rather than have the field silently dropped on the way to
    the CRM. Phase 2's repair loop depends on that failure being raised.
    """

    model_config = ConfigDict(extra="forbid", frozen=False, validate_assignment=True)


class DocumentType(StrEnum):
    """The kinds of inbound document VoltDesk accepts. Closed set."""

    ELECTRICITY_BILL = "electricity_bill"
    SITE_ASSESSMENT = "site_assessment"
    EMAIL_THREAD = "email_thread"


class TaskType(StrEnum):
    """Unit of work the router routes and the evaluator measures, one per row."""

    BILL_EXTRACTION = "bill_extraction"
    SITE_ASSESSMENT_EXTRACTION = "site_assessment_extraction"
    EMAIL_EXTRACTION = "email_extraction"
    KNOWLEDGE_QA = "knowledge_qa"
    SCHEMA_REPAIR = "schema_repair"


class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class ReviewStatus(StrEnum):
    AUTO_APPLIED = "auto_applied"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class CallOutcome(StrEnum):
    SUCCESS = "success"
    SCHEMA_INVALID = "schema_invalid"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    REFUSAL = "refusal"
    CIRCUIT_OPEN = "circuit_open"


Confidence = float
"""Semantic alias for readability. Confidence is always a float in [0, 1]; the
constraint is declared per field via ``Field(ge=0.0, le=1.0)`` so that it survives
JSON Schema export."""


class ExtractedField(StrictModel, Generic[T]):
    """One extracted value plus the evidence and confidence behind it.

    Every field of every extraction contract is wrapped in this. The wrapper is
    what makes the human-review queue and the confidence-band policy in
    docs/GUARDRAILS.md possible: a bare value carries no basis for deciding
    whether it may auto-write to the CRM.
    """

    value: T | None = Field(
        description="The extracted value, or None when the document does not state it."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Model-reported confidence, recalibrated by Phase 2's scorer. "
            "0.0 means 'absent from the document', not 'uncertain'."
        ),
    )
    source_quote: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Verbatim span from the source document supporting the value. Required "
            "whenever value is not None; enforced by Phase 2's validator, not here, "
            "because the generic wrapper cannot see whether T is nullable."
        ),
    )
    source_page: int | None = Field(
        default=None, ge=1, description="1-indexed page the quote came from, for PDFs."
    )


class MoneyAUD(StrictModel):
    """Money is never a bare float in this system."""

    amount: float = Field(description="Amount in Australian dollars.")
    is_gst_inclusive: bool = Field(
        description="Australian retail bills quote GST-inclusive; wholesale tariffs do not."
    )


class DateRange(StrictModel):
    start: date
    end: date

    def days(self) -> int:
        """Inclusive length in days, matching how retailers count a billing period."""
        return (self.end - self.start).days + 1


class Provenance(StrictModel):
    """Where a record came from. Attached to everything written to the CRM."""

    document_id: str = Field(description="Primary key of the source row in app.documents.")
    sha256: str = Field(min_length=64, max_length=64, description="Hash of the source bytes.")
    ingested_at: datetime
    tier: str = Field(
        description=(
            "'A' for real, publicly sourced material; 'B' for synthetic. See "
            "docs/DATA_SOURCES.md. Synthetic records must never be reported as real."
        ),
        pattern="^[AB]$",
    )
