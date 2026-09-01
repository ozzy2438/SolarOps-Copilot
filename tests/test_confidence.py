"""Confidence calibration. Owned by: Phase 2."""

from __future__ import annotations

from helpers_phase2 import DOCUMENT_TEXT, extracted_bill, field, parsed_bill

from voltdesk.extraction.confidence import (
    calibrate,
    classify_for_write,
    min_confidence,
    verify_quote,
)


def test_unverifiable_quote_lowers_confidence() -> None:
    document = parsed_bill(DOCUMENT_TEXT)
    extraction = extracted_bill()
    extraction.retailer_name = field(
        "Northbeam Energy", 0.99, quote="this quote is not in the bill"
    )
    calibrated = calibrate(extraction, document)
    assert calibrated.retailer_name.confidence < 0.99
    assert calibrated.retailer_name.confidence <= 0.5


def test_absent_field_stays_zero() -> None:
    document = parsed_bill(DOCUMENT_TEXT)
    extraction = extracted_bill()
    assert extraction.solar_export_kwh is not None
    extraction.solar_export_kwh = field(None, 0.0, quote=None)
    calibrated = calibrate(extraction, document)
    assert calibrated.solar_export_kwh is not None
    assert calibrated.solar_export_kwh.value is None
    assert calibrated.solar_export_kwh.confidence == 0.0


def test_verify_quote_finds_table_cells() -> None:
    document = parsed_bill("no mention of the rate here")
    document.pages[0].tables = [[["Peak usage", "37.90 c/kWh"]]]
    assert verify_quote("37.90 c/kWh", document) is True
    assert verify_quote("invented", document) is False


def test_classify_for_write_reads_settings() -> None:
    assert classify_for_write("nmi", 0.9) == "auto_write"
    assert classify_for_write("nmi", 0.5) == "review"
    assert classify_for_write("nmi", 0.1) == "drop"


def test_uniform_one_is_treated_as_suspicious() -> None:
    document = parsed_bill(DOCUMENT_TEXT)
    extraction = extracted_bill()
    # Force every present field to 1.0 with real quotes.
    calibrated = calibrate(extraction, document)
    # The fixture already has mixed confidences; stamp 1.0 on present fields.
    from voltdesk.extraction.confidence import iter_extracted_fields

    updates = {}
    for _path, item in iter_extracted_fields(extraction):
        if item.value is not None:
            updates[id(item)] = item.model_copy(update={"confidence": 1.0})
    from voltdesk.extraction.confidence import _replace_fields

    stamped = _replace_fields(extraction, updates)
    calibrated = calibrate(stamped, document)
    present = [
        item.confidence
        for _path, item in iter_extracted_fields(calibrated)
        if item.value is not None
    ]
    assert present
    assert max(present) <= 0.8
    assert min_confidence(calibrated) <= 0.8
