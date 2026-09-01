"""CRM write path.

Owned by: Phase 2. Maps a calibrated extraction to EspoCRM via EspoCrmClient.upsert.
An uncertain NMI on a bill is blocking: nothing from that document is written.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from voltdesk.contracts.common import ExtractedField
from voltdesk.contracts.crm import EnergyProfilePayload, SiteAssessmentPayload
from voltdesk.contracts.documents import (
    ExtractedBill,
    ExtractedEmailThread,
    ExtractedSiteAssessment,
    ExtractionResult,
)
from voltdesk.contracts.review import FieldForReview
from voltdesk.crm.client import EspoCrmClient
from voltdesk.crm.mapping import (
    ENTITY_ENERGY_PROFILE,
    ENTITY_SITE_ASSESSMENT,
    build_energy_profile,
    build_site_assessment,
    payload_to_espo,
)
from voltdesk.extraction.confidence import (
    classify_for_write,
    field_may_auto_write,
    iter_extracted_fields,
    min_confidence,
    nmi_is_uncertain,
    verify_quote,
)
from voltdesk.parsers.base import ParsedDocument


class CrmUpsertClient(Protocol):
    """The slice of EspoCrmClient the writer uses. Tests can supply a fake."""

    def upsert(
        self, entity_type: str, external_key: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]: ...


@dataclass
class WriteOutcome:
    written: bool
    blocking: bool
    entity_type: str | None = None
    external_key: str | None = None
    created: bool | None = None
    review_fields: list[FieldForReview] = field(default_factory=list)


class CrmWriter:
    """Auto-write fields above the threshold; hold the rest for review."""

    def __init__(self, client: CrmUpsertClient | None = None) -> None:
        self._client = client

    def write(self, extraction: ExtractionResult, document: ParsedDocument) -> WriteOutcome:
        review_fields = _fields_for_review(extraction, document)
        if isinstance(extraction, ExtractedBill) and nmi_is_uncertain(extraction, document):
            return WriteOutcome(written=False, blocking=True, review_fields=review_fields)

        if isinstance(extraction, ExtractedEmailThread):
            # Phase 1 defined no email → CRM mapping. Persist extraction only.
            return WriteOutcome(written=False, blocking=False, review_fields=review_fields)

        if isinstance(extraction, ExtractedBill):
            return self._write_bill(extraction, document, review_fields)
        if isinstance(extraction, ExtractedSiteAssessment):
            return self._write_site(extraction, document, review_fields)
        return WriteOutcome(written=False, blocking=False, review_fields=review_fields)

    def _write_bill(
        self,
        extraction: ExtractedBill,
        document: ParsedDocument,
        review_fields: list[FieldForReview],
    ) -> WriteOutcome:
        required = (
            extraction.nmi,
            extraction.billing_period,
            extraction.total_amount,
            extraction.total_consumption_kwh,
            extraction.tariff_type,
        )
        if any(not field_may_auto_write(item, document) for item in required):
            return WriteOutcome(written=False, blocking=False, review_fields=review_fields)
        filtered = extraction.model_copy(
            update={
                "retailer_name": _keep_or_blank(extraction.retailer_name, document),
                "peak_demand_kva": _keep_optional(extraction.peak_demand_kva, document),
                "tariff_code": _keep_optional(extraction.tariff_code, document),
                "solar_export_kwh": _keep_optional(extraction.solar_export_kwh, document),
            }
        )
        confidence = min_confidence(filtered)
        try:
            payload = build_energy_profile(filtered, document.document_id, confidence)
        except ValueError:
            return WriteOutcome(written=False, blocking=False, review_fields=review_fields)
        return self._upsert(ENTITY_ENERGY_PROFILE, payload, review_fields)

    def _write_site(
        self,
        extraction: ExtractedSiteAssessment,
        document: ParsedDocument,
        review_fields: list[FieldForReview],
    ) -> WriteOutcome:
        if not field_may_auto_write(extraction.site_address, document):
            return WriteOutcome(written=False, blocking=False, review_fields=review_fields)
        filtered = extraction.model_copy(
            update={
                "nmi": _keep_optional(extraction.nmi, document),
                "assessed_on": _keep_optional(extraction.assessed_on, document),
                "roof_material": _keep_optional(extraction.roof_material, document),
                "phase_configuration": _keep_optional(
                    extraction.phase_configuration, document
                ),
                "main_switch_rating_a": _keep_optional(
                    extraction.main_switch_rating_a, document
                ),
                "existing_pv_kw": _keep_optional(extraction.existing_pv_kw, document),
                "battery_space_available": _keep_optional(
                    extraction.battery_space_available, document
                ),
                "access_constraints": _keep_optional(
                    extraction.access_constraints, document
                ),
            }
        )
        confidence = min_confidence(filtered)
        try:
            payload = build_site_assessment(filtered, document.document_id, confidence)
        except ValueError:
            return WriteOutcome(written=False, blocking=False, review_fields=review_fields)
        return self._upsert(ENTITY_SITE_ASSESSMENT, payload, review_fields)

    def _upsert(
        self,
        entity_type: str,
        payload: EnergyProfilePayload | SiteAssessmentPayload,
        review_fields: list[FieldForReview],
    ) -> WriteOutcome:
        if self._client is not None:
            record, created = self._client.upsert(
                entity_type, payload.external_key, payload_to_espo(payload)
            )
        else:
            with EspoCrmClient() as client:
                record, created = client.upsert(
                    entity_type, payload.external_key, payload_to_espo(payload)
                )
        _ = record
        return WriteOutcome(
            written=True,
            blocking=False,
            entity_type=entity_type,
            external_key=payload.external_key,
            created=created,
            review_fields=review_fields,
        )


def _keep_or_blank(
    extracted: ExtractedField[Any], document: ParsedDocument
) -> ExtractedField[Any]:
    if field_may_auto_write(extracted, document):
        return extracted
    return extracted.model_copy(update={"value": None, "confidence": 0.0})


def _keep_optional(
    extracted: ExtractedField[Any] | None, document: ParsedDocument
) -> ExtractedField[Any] | None:
    if extracted is None:
        return None
    if field_may_auto_write(extracted, document):
        return extracted
    return None


def _fields_for_review(
    extraction: ExtractionResult, document: ParsedDocument
) -> list[FieldForReview]:
    items: list[FieldForReview] = []
    for path, extracted in iter_extracted_fields(extraction):
        if not isinstance(extracted, ExtractedField):
            continue
        band = classify_for_write(path, extracted.confidence)
        unverified = bool(
            extracted.value is not None
            and extracted.source_quote
            and not verify_quote(extracted.source_quote, document)
        )
        is_nmi = path == "nmi"
        if band == "auto_write" and not unverified:
            continue
        if band == "drop" and extracted.value is None and not is_nmi:
            continue
        reason = _reason(path, band, unverified, extracted)
        items.append(
            FieldForReview(
                field_path=path,
                proposed_value=_proposed(extracted.value),
                confidence=extracted.confidence,
                source_quote=extracted.source_quote,
                source_page=extracted.source_page,
                reason=reason,
            )
        )
    return items


def _proposed(value: object) -> object:
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return value


def _reason(path: str, band: str, unverified: bool, field: ExtractedField[object]) -> str:
    if path == "nmi" or path.endswith(".nmi"):
        return "The NMI is the join key. It cannot go to the CRM until a person confirms it."
    if unverified:
        return "The cited quote was not found in the document, so this value looks invented."
    if band == "drop":
        return "Confidence is below the review floor; treated as no signal unless you correct it."
    if field.value is None:
        return "The document does not appear to state this field."
    return "Confidence is below the auto-write threshold."
