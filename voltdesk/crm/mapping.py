"""Extraction contract -> EspoCRM payload mapping.

Owned by: Phase 1 (the declarative tables and key derivation). Phase 2 implements
`build_*` functions that consume these tables.

The mapping is data, not code, so that a human can read it next to
crm/espocrm_entities.md and see that the two agree.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any

from voltdesk.contracts.common import ExtractedField
from voltdesk.contracts.crm import EnergyProfilePayload, SiteAssessmentPayload
from voltdesk.contracts.documents import ExtractedBill, ExtractedSiteAssessment

#: VoltDesk contract field path -> EspoCRM attribute name, per entity type.
#: A contract field absent from this table is deliberately not written to the CRM.
BILL_TO_ENERGY_PROFILE: dict[str, str] = {
    "nmi": "nmi",
    "retailer_name": "retailerName",
    "billing_period.start": "billingPeriodStart",
    "billing_period.end": "billingPeriodEnd",
    "total_consumption_kwh": "totalConsumptionKwh",
    "peak_demand_kva": "peakDemandKva",
    "total_amount.amount": "totalAmountAud",
    "tariff_type": "tariffType",
    "tariff_code": "tariffCode",
    "solar_export_kwh": "solarExportKwh",
}

SITE_ASSESSMENT_TO_CRM: dict[str, str] = {
    "site_address": "siteAddress",
    "nmi": "nmi",
    "assessed_on": "assessedOn",
    "roof_material": "roofMaterial",
    "phase_configuration": "phaseConfiguration",
    "main_switch_rating_a": "mainSwitchRatingA",
    "existing_pv_kw": "existingPvKw",
    "battery_space_available": "batterySpaceAvailable",
    "access_constraints": "accessConstraints",
}

#: Fields that are never written to the CRM, and why. Phase 2 must not "fix" these.
WITHHELD_FIELDS: dict[str, str] = {
    "account_number": "PII with no CRM use; redacted before the model sees it.",
    "assessor_name": "Staff PII; the CRM already knows who owns the record.",
    "participant_emails": "PII; the CRM's own email tracking owns this.",
    "parser_warnings": "Operational detail; belongs in app.extractions, not the CRM.",
}

#: EspoCRM entity type names. Must match crm/espocrm_entities.md exactly.
ENTITY_ENERGY_PROFILE = "EnergyProfile"
ENTITY_SITE_ASSESSMENT = "SiteAssessment"
ENTITY_GRID_CONNECTION = "GridConnection"
ENTITY_PROPOSAL = "Proposal"


def energy_profile_key(nmi: str, period_start: str, period_end: str) -> str:
    """Idempotency key for a bill.

    Derived from facts on the document, never from a UUID we generated: reprocessing
    the same bill must land on the same key. NMI plus billing period identifies a
    bill uniquely for a site even when the retailer changes.
    """
    return f"bill:{nmi}:{period_start}:{period_end}"


def site_assessment_key(site_address: str, assessed_on: str) -> str:
    """Address is normalised by lowercasing and collapsing whitespace before hashing,
    so that '12 Example St' and '12  example st' do not create two records."""
    normalised = " ".join(site_address.lower().split())
    digest = hashlib.sha256(normalised.encode()).hexdigest()[:16]
    return f"site:{digest}:{assessed_on}"


def build_energy_profile(
    extraction: ExtractedBill, source_document_id: str, confidence: float
) -> EnergyProfilePayload:
    """Map a bill extraction onto the EnergyProfile CRM payload."""
    nmi = extraction.nmi.value
    period = extraction.billing_period.value
    amount = extraction.total_amount.value
    consumption = extraction.total_consumption_kwh.value
    tariff_type = extraction.tariff_type.value
    if not nmi or period is None or amount is None or consumption is None or tariff_type is None:
        raise ValueError(
            "EnergyProfile requires nmi, billing period, amount, consumption, tariff type"
        )
    start = period.start.isoformat()
    end = period.end.isoformat()
    return EnergyProfilePayload(
        external_key=energy_profile_key(nmi, start, end),
        source_document_id=source_document_id,
        extraction_confidence=confidence,
        name=f"{nmi} {start}–{end}",
        nmi=nmi,
        retailerName=_str_or_none(extraction.retailer_name),
        billingPeriodStart=period.start,
        billingPeriodEnd=period.end,
        totalConsumptionKwh=consumption,
        peakDemandKva=_float_or_none(extraction.peak_demand_kva),
        totalAmountAud=amount.amount,
        tariffType=str(tariff_type),
        tariffCode=_str_or_none(extraction.tariff_code),
        solarExportKwh=_float_or_none(extraction.solar_export_kwh),
    )


def build_site_assessment(
    extraction: ExtractedSiteAssessment, source_document_id: str, confidence: float
) -> SiteAssessmentPayload:
    address = extraction.site_address.value
    if not address:
        raise ValueError("SiteAssessment requires site_address")
    assessed = _as_date(_optional(extraction.assessed_on))
    assessed_key = assessed.isoformat() if assessed is not None else "unknown"
    hazards = [
        str(item.value)
        for item in extraction.hazards
        if isinstance(item, ExtractedField) and item.value
    ]
    phase = extraction.phase_configuration
    return SiteAssessmentPayload(
        external_key=site_assessment_key(address, assessed_key),
        source_document_id=source_document_id,
        extraction_confidence=confidence,
        name=f"{address} – {assessed_key}",
        siteAddress=address,
        nmi=_str_or_none(extraction.nmi),
        assessedOn=assessed,
        roofMaterial=_str_or_none(extraction.roof_material),
        usableRoofAreaM2=_roof_area(extraction),
        phaseConfiguration=(
            str(phase.value) if phase is not None and phase.value else None
        ),
        mainSwitchRatingA=_float_or_none(extraction.main_switch_rating_a),
        existingPvKw=_float_or_none(extraction.existing_pv_kw),
        batterySpaceAvailable=_bool_or_none(extraction.battery_space_available),
        hazards="\n".join(hazards) if hazards else None,
        accessConstraints=_str_or_none(extraction.access_constraints),
    )


def payload_to_espo(payload: EnergyProfilePayload | SiteAssessmentPayload) -> dict[str, object]:
    """Translate contract field names to EspoCRM attribute names. Do not send
    `external_key` — EspoCrmClient.upsert adds voltdeskExternalKey itself.
    """
    data = payload.model_dump(mode="json")
    data.pop("external_key")
    data["voltdeskSourceDocumentId"] = data.pop("source_document_id")
    data["voltdeskExtractionConfidence"] = data.pop("extraction_confidence")
    return data


def _optional(field: ExtractedField[Any] | None) -> Any:
    if field is None:
        return None
    return field.value


def _str_or_none(field: ExtractedField[Any] | None) -> str | None:
    value = _optional(field)
    return str(value) if value is not None else None


def _float_or_none(field: ExtractedField[Any] | None) -> float | None:
    value = _optional(field)
    if value is None:
        return None
    return float(value)


def _bool_or_none(field: ExtractedField[Any] | None) -> bool | None:
    value = _optional(field)
    if value is None:
        return None
    return bool(value)


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _roof_area(extraction: ExtractedSiteAssessment) -> float | None:
    total = 0.0
    found = False
    for plane in extraction.roof_planes:
        area = plane.usable_area_m2
        if area is not None and area.value is not None:
            total += float(area.value)
            found = True
    return total if found else None
