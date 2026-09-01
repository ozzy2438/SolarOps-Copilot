"""Extraction contracts: what VoltDesk pulls out of each inbound document type.

Owned by: Phase 1 (definition). Phase 2 populates these; Phase 4 measures them.
Every business field is an ExtractedField so that confidence and evidence travel
with the value all the way to the CRM write decision.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field

from voltdesk.contracts.common import (
    DateRange,
    DocumentType,
    ExtractedField,
    MoneyAUD,
    Provenance,
    StrictModel,
)


class TariffType(StrEnum):
    """Retail tariff structures seen on Australian commercial bills."""

    FLAT = "flat"
    TIME_OF_USE = "time_of_use"
    DEMAND = "demand"
    UNKNOWN = "unknown"


class PhaseConfiguration(StrEnum):
    SINGLE_PHASE = "single_phase"
    THREE_PHASE = "three_phase"
    UNKNOWN = "unknown"


class TariffComponent(StrictModel):
    """One priced line on a bill. Bills carry several; keep them, do not average."""

    label: ExtractedField[str] = Field(description="Retailer's own name for the component.")
    rate_c_per_kwh: ExtractedField[float] | None = Field(
        default=None, description="Usage rate in cents per kWh, if this is a usage component."
    )
    daily_supply_c: ExtractedField[float] | None = Field(
        default=None, description="Daily supply charge in cents per day, if applicable."
    )
    demand_rate_c_per_kva: ExtractedField[float] | None = Field(
        default=None, description="Demand charge, for demand tariffs."
    )
    quantity: ExtractedField[float] | None = Field(
        default=None, description="Billed quantity for this component."
    )


class ExtractedBill(StrictModel):
    """A commercial electricity bill, parsed.

    The NMI is the join key to everything else in the Australian market and is the
    single most important field on this model; an extraction without it cannot be
    matched to a site and must go to review regardless of its other confidences.
    """

    document_type: DocumentType = DocumentType.ELECTRICITY_BILL
    provenance: Provenance

    retailer_name: ExtractedField[str]
    account_number: ExtractedField[str] = Field(
        description="Redacted before any third-party API call; see docs/GUARDRAILS.md."
    )
    nmi: ExtractedField[str] = Field(
        description=(
            "National Metering Identifier. 10 or 11 characters. "
            "TODO(verify): confirm the checksum rule against the AEMO NMI Procedure "
            "before enforcing a pattern here - Phase 2 must not invent one."
        )
    )
    site_address: ExtractedField[str]
    billing_period: ExtractedField[DateRange]
    issue_date: ExtractedField[date] | None = None

    total_amount: ExtractedField[MoneyAUD]
    total_consumption_kwh: ExtractedField[float]
    peak_demand_kva: ExtractedField[float] | None = None
    tariff_type: ExtractedField[TariffType]
    tariff_code: ExtractedField[str] | None = None
    components: list[TariffComponent] = Field(
        default_factory=list, description="Every priced line item found, in bill order."
    )
    solar_export_kwh: ExtractedField[float] | None = Field(
        default=None, description="Present only when the site already has generation."
    )
    phase_configuration: ExtractedField[PhaseConfiguration] | None = None

    page_count: int = Field(ge=1, description="Pages in the source PDF.")
    parser_warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal parse problems (skew, OCR fallback, ambiguous date format).",
    )


class RoofOrientation(StrEnum):
    N = "N"
    NE = "NE"
    E = "E"
    SE = "SE"
    S = "S"
    SW = "SW"
    W = "W"
    NW = "NW"
    FLAT = "flat"
    MIXED = "mixed"


class RoofPlane(StrictModel):
    """One usable roof plane. A commercial site typically has several."""

    orientation: ExtractedField[RoofOrientation]
    tilt_degrees: ExtractedField[float] | None = Field(
        default=None, description="0 = flat, 90 = vertical."
    )
    usable_area_m2: ExtractedField[float] | None = None
    shading_notes: ExtractedField[str] | None = None


class ExtractedSiteAssessment(StrictModel):
    """An installer's site visit notes, parsed. Often handwritten and photographed."""

    document_type: DocumentType = DocumentType.SITE_ASSESSMENT
    provenance: Provenance

    site_address: ExtractedField[str]
    nmi: ExtractedField[str] | None = None
    assessed_on: ExtractedField[date] | None = None
    assessor_name: ExtractedField[str] | None = Field(
        default=None, description="Staff name. Redacted before third-party calls."
    )

    roof_material: ExtractedField[str] | None = None
    roof_planes: list[RoofPlane] = Field(default_factory=list)
    switchboard_notes: ExtractedField[str] | None = None
    phase_configuration: ExtractedField[PhaseConfiguration] | None = None
    main_switch_rating_a: ExtractedField[float] | None = None
    existing_pv_kw: ExtractedField[float] | None = None
    battery_space_available: ExtractedField[bool] | None = None
    access_constraints: ExtractedField[str] | None = None
    hazards: list[ExtractedField[str]] = Field(
        default_factory=list, description="Asbestos, height, live parts, restricted access."
    )

    parser_warnings: list[str] = Field(default_factory=list)


class EmailIntent(StrEnum):
    NEW_ENQUIRY = "new_enquiry"
    QUOTE_REQUEST = "quote_request"
    TECHNICAL_QUESTION = "technical_question"
    SCHEDULING = "scheduling"
    COMPLAINT = "complaint"
    OTHER = "other"


class ExtractedEmailThread(StrictModel):
    """An inbound email thread, reduced to the facts the CRM cares about."""

    document_type: DocumentType = DocumentType.EMAIL_THREAD
    provenance: Provenance

    thread_subject: ExtractedField[str]
    participant_emails: list[ExtractedField[str]] = Field(
        default_factory=list, description="Redacted before third-party calls."
    )
    first_message_at: ExtractedField[datetime] | None = None
    last_message_at: ExtractedField[datetime] | None = None
    message_count: int = Field(ge=1)

    intent: ExtractedField[EmailIntent]
    company_name: ExtractedField[str] | None = None
    site_address: ExtractedField[str] | None = None
    requested_system_kw: ExtractedField[float] | None = None
    requested_battery_kwh: ExtractedField[float] | None = None
    deadline: ExtractedField[date] | None = None
    summary: ExtractedField[str] = Field(description="Two sentences at most, for the CRM note.")

    parser_warnings: list[str] = Field(default_factory=list)


ExtractionResult = ExtractedBill | ExtractedSiteAssessment | ExtractedEmailThread
"""Discriminate on `document_type` when narrowing this union."""
