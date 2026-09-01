"""Extraction contract -> EspoCRM payload mapping.

Owned by: Phase 1 (the declarative tables and key derivation). Phase 2 implements
`build_*` functions that consume these tables.

The mapping is data, not code, so that a human can read it next to
crm/espocrm_entities.md and see that the two agree.
"""

from __future__ import annotations

import hashlib

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
