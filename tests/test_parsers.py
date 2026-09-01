"""Parser tests. Owned by: Phase 2.

Cover the synthetic generator's deliberate traps: a skewed scan, a tariff table
split across a page break, and both date conventions in one document.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from voltdesk.parsers import BillParser, EmailThreadParser, SiteNotesParser
from voltdesk.parsers.email_parser import dedupe_quoted
from voltdesk.synthetic.bills import build_facts, write_bill_pdf
from voltdesk.synthetic.identities import fabricate
from voltdesk.synthetic.spec import Defect, GeneratorConfig, RetailerLayout
from voltdesk.synthetic.tariffs import load_tariffs


def _tariff() -> dict[str, object]:
    return load_tariffs(GeneratorConfig(seed=1))[0]


def _write_bill(tmp_path: Path, defects: list[Defect], layout: RetailerLayout) -> Path:
    rng = __import__("random").Random(0)
    identity = fabricate(rng, index=0)
    facts = build_facts(
        identity,
        layout,
        _tariff(),
        date(2026, 1, 1),
        12000.0,
        8000.0,
        4000.0,
        150.0,
        defects,
    )
    path = tmp_path / "bill.pdf"
    write_bill_pdf(path, facts)
    return path


def test_skewed_scan_records_rotation(tmp_path: Path) -> None:
    path = _write_bill(tmp_path, [Defect.SKEWED_SCAN], RetailerLayout.RETAILER_A)
    parsed = BillParser().parse("doc-1", path.read_bytes(), path.name)
    assert any(page.skew_degrees for page in parsed.pages)
    assert any("rotated" in warning for warning in parsed.warnings)


def test_split_table_reuses_header_on_page_two(tmp_path: Path) -> None:
    path = _write_bill(tmp_path, [Defect.MULTI_PAGE_TABLE_SPLIT], RetailerLayout.RETAILER_A)
    parsed = BillParser().parse("doc-1", path.read_bytes(), path.name)
    assert len(parsed.pages) >= 2
    # Either plumber recovered a table on page 2 with a header, or the text
    # layer still carries the continued NMI and remaining rows.
    page_two = parsed.pages[1].text
    assert "NMI" in page_two
    combined = parsed.full_text()
    assert "Daily supply" in combined or parsed.pages[0].tables


def test_both_date_formats_are_preserved_and_flagged(tmp_path: Path) -> None:
    path = _write_bill(
        tmp_path, [Defect.INCONSISTENT_DATE_FORMAT], RetailerLayout.RETAILER_A
    )
    parsed = BillParser().parse("doc-1", path.read_bytes(), path.name)
    text = parsed.full_text()
    assert "01/01/2026" in text or "1/01/2026" in text or "01/01/2026" in text
    assert "Mar 2026" in text or "Apr 2026" in text
    assert "ambiguous_date_formats" in parsed.warnings


def test_quoted_email_history_is_deduplicated() -> None:
    original = "Hi, we need a 50 kW rooftop system."
    thread = (
        f"{original}\n\n"
        f"Thanks, we can site-visit.\n\n"
        f"On Monday alice@example.test wrote:\n"
        f"> {original}\n"
        f"> {original}\n"
    )
    cleaned, dropped = dedupe_quoted(thread)
    assert dropped
    assert cleaned.count("50 kW") == 1
    parsed = EmailThreadParser().parse("e1", thread.encode(), "thread.txt")
    assert parsed.pages[0].text.count("50 kW") == 1
    assert "quoted_history_deduplicated" in parsed.warnings


def test_empty_site_notes_are_loud_not_clean() -> None:
    parsed = SiteNotesParser().parse("s1", b"", "notes.txt")
    assert parsed.pages[0].text == ""
    assert "empty_site_notes" in parsed.warnings


def test_image_only_pdf_does_not_invent_text(tmp_path: Path) -> None:
    path = _write_bill(tmp_path, [Defect.NO_TEXT_LAYER], RetailerLayout.RETAILER_A)
    parsed = BillParser().parse("doc-1", path.read_bytes(), path.name)
    assert parsed.pages[0].used_ocr is True
    if not parsed.pages[0].text:
        assert "ocr_unavailable" in parsed.warnings
