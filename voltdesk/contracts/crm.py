"""EspoCRM entity payloads.

Owned by: Phase 1. The field names here are EspoCRM attribute names, not VoltDesk
names, because these objects are serialised straight onto the CRM REST API. The
mapping from extraction contracts to these payloads lives in voltdesk/crm/mapping.py
and is documented for a human in crm/espocrm_entities.md.

TODO(verify): the custom entity and field definitions in crm/espocrm_entities.md must
actually be created in the EspoCRM instance before these payloads will be accepted.
Phase 2 verifies this against a live instance; Phase 1 did not.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field

from voltdesk.contracts.common import StrictModel


class CrmEntity(StrictModel):
    """Common shape for every CRM payload VoltDesk writes.

    `external_key` is what makes writes idempotent. It is derived from stable
    document facts (NMI plus billing period, for instance), never from a UUID we
    generated, so that re-processing the same document twice updates one record
    instead of creating two.
    """

    external_key: str = Field(
        min_length=1,
        description="Value written to the CRM's voltdeskExternalKey field. Unique per entity.",
    )
    source_document_id: str = Field(description="app.documents.id of the document behind this.")
    extraction_confidence: float = Field(
        ge=0.0, le=1.0, description="Minimum confidence across the fields that populated this."
    )


class SiteAssessmentPayload(CrmEntity):
    """EspoCRM custom entity `SiteAssessment`."""

    name: str = Field(description="Display name, e.g. '12 Example St - 2026-03-04'.")
    siteAddress: str
    nmi: str | None = None
    assessedOn: date | None = None
    roofMaterial: str | None = None
    usableRoofAreaM2: float | None = None
    phaseConfiguration: str | None = None
    mainSwitchRatingA: float | None = None
    existingPvKw: float | None = None
    batterySpaceAvailable: bool | None = None
    hazards: str | None = Field(default=None, description="Newline-joined hazard list.")
    accessConstraints: str | None = None


class EnergyProfilePayload(CrmEntity):
    """EspoCRM custom entity `EnergyProfile`. One per bill, per site."""

    name: str
    nmi: str
    retailerName: str | None = None
    billingPeriodStart: date
    billingPeriodEnd: date
    totalConsumptionKwh: float
    peakDemandKva: float | None = None
    totalAmountAud: float
    tariffType: str
    tariffCode: str | None = None
    solarExportKwh: float | None = None


class GridConnectionPayload(CrmEntity):
    """EspoCRM custom entity `GridConnection`."""

    name: str
    nmi: str
    dnspName: str | None = Field(
        default=None,
        description=(
            "Distribution network service provider. "
            "TODO(verify): NMI-to-DNSP mapping is published per jurisdiction; Phase 3 "
            "must source it rather than infer it from the postcode."
        ),
    )
    exportLimitKw: float | None = None
    connectionStatus: str | None = None
    applicationReference: str | None = None


class ProposalPayload(CrmEntity):
    """EspoCRM custom entity `Proposal`.

    VoltDesk populates the technical fields only. Generating customer-facing
    proposal documents is permanently out of scope (docs/SCOPE.md).
    """

    name: str
    siteAddress: str
    proposedPvKw: float | None = None
    proposedBatteryKwh: float | None = None
    estimatedAnnualSavingsAud: float | None = None
    status: str | None = None


CrmPayload = (
    SiteAssessmentPayload | EnergyProfilePayload | GridConnectionPayload | ProposalPayload
)
