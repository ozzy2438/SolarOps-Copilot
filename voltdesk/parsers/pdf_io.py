"""PDF helpers for parsers. Owned by: Phase 2. Never calls a model."""

from __future__ import annotations

import hashlib
import io
from typing import Any


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def looks_like_pdf(content: bytes) -> bool:
    return content[:5] == b"%PDF-"


def page_rotation_degrees(content: bytes) -> list[float | None]:
    """Per-page /Rotate values. None when the page has no rotation."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    degrees: list[float | None] = []
    for page in reader.pages:
        rotation = page.get("/Rotate")
        if rotation is None:
            degrees.append(None)
        else:
            degrees.append(float(rotation) % 360)
    return degrees


def extract_pdf_pages(content: bytes) -> list[tuple[str, list[list[list[str]]], bool]]:
    """Return (text, tables, used_ocr) per page. used_ocr is True when the text
    layer is empty. OCR is not invented: if tesseract is absent the text stays
    empty and the caller records a warning.
    """
    import pdfplumber

    pages: list[tuple[str, list[list[list[str]]], bool]] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = (page.extract_text() or "").strip()
            tables = _tables_from(page)
            used_ocr = not text
            if used_ocr:
                ocr_text = _try_ocr(page)
                if ocr_text:
                    text = ocr_text
            pages.append((text, tables, used_ocr))
    return pages


def _tables_from(page: Any) -> list[list[list[str]]]:
    found = page.extract_tables() or []
    tables: list[list[list[str]]] = []
    for table in found:
        rows = [[(cell or "").strip() for cell in row] for row in table]
        if any(any(cell for cell in row) for row in rows):
            tables.append(rows)
    return tables


def _try_ocr(page: Any) -> str:
    try:
        import pytesseract
    except ImportError:
        return ""
    image = page.to_image(resolution=150).original
    try:
        return pytesseract.image_to_string(image) or ""
    except Exception:  # noqa: BLE001 - missing binary is a warning, not a crash
        return ""


def stitch_split_tables(pages_tables: list[list[list[list[str]]]]) -> list[list[list[list[str]]]]:
    """If page 2+ has rows but no header, reuse the previous page's header.

    A tariff table that continues without repeating 'Component' / 'Rate' would
    otherwise become a headerless grid and lose the rate-to-label association.
    """
    if not pages_tables:
        return pages_tables
    stitched: list[list[list[list[str]]]] = []
    last_header: list[str] | None = None
    for tables in pages_tables:
        page_out: list[list[list[str]]] = []
        for table in tables:
            if not table:
                continue
            header = table[0]
            if _looks_like_header(header):
                last_header = header
                page_out.append(table)
            elif last_header is not None:
                page_out.append([last_header, *table])
            else:
                page_out.append(table)
        stitched.append(page_out)
    return stitched


def _looks_like_header(row: list[str]) -> bool:
    joined = " ".join(row).lower()
    return any(token in joined for token in ("component", "rate", "quantity", "amount", "label"))
