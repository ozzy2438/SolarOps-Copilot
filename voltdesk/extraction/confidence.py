"""Confidence scoring and calibration.

Owned by: Phase 2. See docs/PHASE_2.md.

A raw model-reported confidence is not calibrated - models are systematically
overconfident. Phase 2 must produce a score that can be thresholded against
VOLTDESK_AUTO_WRITE_CONFIDENCE_THRESHOLD and mean something. The evidence available
for calibration: whether a `source_quote` was returned and whether it actually
appears in the document, agreement across a repeated call, and format validity of
the value itself.

Phase 4 measures whether the calibration holds, via the coverage-accuracy curve in
docs/EVALUATION.md.
"""

from __future__ import annotations

import re
from typing import Any, cast

from voltdesk.config import get_settings
from voltdesk.contracts.common import ExtractedField
from voltdesk.contracts.documents import ExtractionResult
from voltdesk.parsers.base import ParsedDocument

_UNIFORM_CEILING = 0.8
_UNVERIFIED_FACTOR = 0.4
_MISSING_QUOTE_FACTOR = 0.5


def verify_quote(quote: str | None, document: ParsedDocument) -> bool:
    """Does the cited quote actually appear in the document?

    This is the single strongest calibration signal available and it costs nothing:
    a model that invented a value usually invents the quote too.
    """
    if not quote or not quote.strip():
        return False
    haystack = _normalise(document.full_text())
    needle = _normalise(quote)
    if needle and needle in haystack:
        return True
    for page in document.pages:
        for table in page.tables:
            cells = _normalise(" ".join(cell for row in table for cell in row))
            if needle in cells:
                return True
    return False


def calibrate(
    extraction: ExtractionResult, document: ParsedDocument
) -> ExtractionResult:
    """Return the extraction with recalibrated per-field confidences."""
    fields = list(iter_extracted_fields(extraction))
    present = [
        field
        for _, field in fields
        if field.value is not None or field.confidence > 0.0
    ]
    uniform = bool(present) and all(field.confidence >= 0.999 for field in present)
    updates: dict[int, ExtractedField[Any]] = {}
    for path, field in fields:
        calibrated = _calibrate_one(field, document)
        if uniform and calibrated.value is not None and calibrated.confidence > _UNIFORM_CEILING:
            calibrated = calibrated.model_copy(update={"confidence": _UNIFORM_CEILING})
        updates[id(field)] = calibrated
        _ = path
    return cast(ExtractionResult, _replace_fields(extraction, updates))


def classify_for_write(field_path: str, confidence: float) -> str:
    """Which confidence band this field falls into.

    Returns one of 'auto_write', 'review', 'drop'. The bands are defined in
    docs/GUARDRAILS.md and read from settings, not hard-coded here.
    An unverifiable quote is never auto-write; callers combine this with
    `verify_quote` (see `field_may_auto_write`).
    """
    _ = field_path
    settings = get_settings()
    if confidence >= settings.auto_write_confidence_threshold:
        return "auto_write"
    if confidence >= settings.review_floor_confidence:
        return "review"
    return "drop"


def field_may_auto_write(field: ExtractedField[Any], document: ParsedDocument) -> bool:
    """Auto-write requires the auto-write band and a quote found in the document."""
    if field.value is None:
        return False
    if classify_for_write("field", field.confidence) != "auto_write":
        return False
    return verify_quote(field.source_quote, document)


def min_confidence(extraction: Any) -> float:
    """Lowest confidence across every ExtractedField in the extraction."""
    fields = [field for _, field in iter_extracted_fields(extraction)]
    if not fields:
        return 0.0
    return min(field.confidence for field in fields)


def nmi_is_uncertain(extraction: ExtractionResult, document: ParsedDocument) -> bool:
    """A bill whose NMI is below auto-write, absent, or unverifiable is blocking."""
    nmi = getattr(extraction, "nmi", None)
    if nmi is None or not isinstance(nmi, ExtractedField):
        return False
    if nmi.value is None:
        return True
    if not verify_quote(nmi.source_quote, document):
        return True
    return classify_for_write("nmi", nmi.confidence) != "auto_write"


def _calibrate_one(field: ExtractedField[Any], document: ParsedDocument) -> ExtractedField[Any]:
    if field.value is None and field.confidence == 0.0:
        return field
    if field.value is not None and not field.source_quote:
        return field.model_copy(
            update={"confidence": min(field.confidence, _MISSING_QUOTE_FACTOR)}
        )
    if field.source_quote and not verify_quote(field.source_quote, document):
        return field.model_copy(
            update={"confidence": min(field.confidence * _UNVERIFIED_FACTOR, 0.5)}
        )
    return field


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def iter_extracted_fields(obj: Any, prefix: str = "") -> list[tuple[str, ExtractedField[Any]]]:
    found: list[tuple[str, ExtractedField[Any]]] = []
    if isinstance(obj, ExtractedField):
        found.append((prefix or "field", obj))
        if obj.value is not None and not isinstance(obj.value, (str, int, float, bool)):
            found.extend(iter_extracted_fields(obj.value, prefix))
        return found
    if isinstance(obj, list):
        for index, item in enumerate(obj):
            child = f"{prefix}.{index}" if prefix else str(index)
            found.extend(iter_extracted_fields(item, child))
        return found
    model_fields = getattr(type(obj), "model_fields", None)
    if isinstance(model_fields, dict):
        for name in model_fields:
            child = f"{prefix}.{name}" if prefix else name
            found.extend(iter_extracted_fields(getattr(obj, name), child))
    return found


def _replace_fields(obj: Any, updates: dict[int, ExtractedField[Any]]) -> Any:
    if isinstance(obj, ExtractedField):
        replacement = updates.get(id(obj), obj)
        if replacement.value is not None and not isinstance(
            replacement.value, (str, int, float, bool)
        ):
            new_value = _replace_fields(replacement.value, updates)
            return replacement.model_copy(update={"value": new_value})
        return replacement
    if isinstance(obj, list):
        return [_replace_fields(item, updates) for item in obj]
    model_fields = getattr(type(obj), "model_fields", None)
    if isinstance(model_fields, dict) and hasattr(obj, "model_copy"):
        changes = {
            name: _replace_fields(getattr(obj, name), updates) for name in model_fields
        }
        return obj.model_copy(update=changes)
    return obj
