"""Shared extraction builders for Phase 2 tests. Not production code."""

from __future__ import annotations

from datetime import UTC, date, datetime

from voltdesk.contracts.common import (
    DateRange,
    DocumentType,
    ExtractedField,
    MoneyAUD,
    Provenance,
)
from voltdesk.contracts.documents import ExtractedBill, TariffType
from voltdesk.parsers.base import ParsedDocument, ParsedPage


def field(
    value: object, confidence: float = 0.92, quote: str | None = None
) -> ExtractedField[object]:
    if quote is not None:
        source_quote = quote
    elif value is None:
        source_quote = None
    else:
        source_quote = str(value)
    return ExtractedField(
        value=value,
        confidence=confidence,
        source_quote=source_quote,
        source_page=1,
    )


def provenance() -> Provenance:
    return Provenance(
        document_id="doc-1",
        sha256="a" * 64,
        ingested_at=datetime(2026, 3, 1, tzinfo=UTC),
        tier="B",
    )


def parsed_bill(text: str, document_id: str = "doc-1") -> ParsedDocument:
    return ParsedDocument(
        document_id=document_id,
        document_type=DocumentType.ELECTRICITY_BILL,
        sha256="a" * 64,
        pages=[
            ParsedPage(
                page_number=1,
                text=text,
                tables=[[["Component", "Rate"]]],
                used_ocr=False,
            )
        ],
    )


def extracted_bill(
    *,
    nmi: str | None = "6305888444",
    nmi_confidence: float = 0.95,
    nmi_quote: str | None = "NMI 6305888444",
) -> ExtractedBill:
    absent: ExtractedField[float | None] = ExtractedField(
        value=None, confidence=0.0, source_quote=None, source_page=None
    )
    return ExtractedBill(
        document_type=DocumentType.ELECTRICITY_BILL,
        provenance=provenance(),
        retailer_name=field("Northbeam Energy", quote="Northbeam Energy"),
        account_number=field("4029183746", quote="Account 4029183746"),
        nmi=ExtractedField(
            value=nmi,
            confidence=nmi_confidence if nmi is not None else 0.0,
            source_quote=nmi_quote,
            source_page=1,
        ),
        site_address=field(
            "14 Kerrigan Way, Dandenong South VIC 3175",
            quote="14 Kerrigan Way",
        ),
        billing_period=field(
            DateRange(start=date(2026, 1, 1), end=date(2026, 3, 31)),
            quote="01/01/2026 to 31/03/2026",
        ),
        issue_date=field(date(2026, 4, 8), quote="08/04/2026"),
        total_amount=field(
            MoneyAUD(amount=8421.55, is_gst_inclusive=True), quote="8421.55"
        ),
        total_consumption_kwh=field(41230.0, quote="41230"),
        peak_demand_kva=absent,
        tariff_type=field(TariffType.FLAT, quote="flat"),
        tariff_code=field("NB-COM-FLAT", quote="NB-COM-FLAT"),
        solar_export_kwh=ExtractedField(value=None, confidence=0.0),
        page_count=1,
    )


DOCUMENT_TEXT = (
    "Northbeam Energy Account 4029183746 NMI 6305888444 "
    "14 Kerrigan Way, Dandenong South VIC 3175 "
    "01/01/2026 to 31/03/2026 Issue 08/04/2026 "
    "Total 8421.55 AUD GST inclusive 41230 kWh tariff NB-COM-FLAT flat"
)
