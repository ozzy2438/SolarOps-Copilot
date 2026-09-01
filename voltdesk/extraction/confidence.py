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

from typing import Any

from voltdesk.contracts.documents import ExtractionResult
from voltdesk.parsers.base import ParsedDocument


def verify_quote(quote: str | None, document: ParsedDocument) -> bool:
    """Does the cited quote actually appear in the document?

    This is the single strongest calibration signal available and it costs nothing:
    a model that invented a value usually invents the quote too.
    """
    raise NotImplementedError(
        "verify_quote is implemented in Phase 2 (docs/PHASE_2.md, step 6)"
    )


def calibrate(
    extraction: ExtractionResult, document: ParsedDocument
) -> ExtractionResult:
    """Return the extraction with recalibrated per-field confidences."""
    raise NotImplementedError(
        "calibrate is implemented in Phase 2 (docs/PHASE_2.md, step 6)"
    )


def classify_for_write(field_path: str, confidence: float) -> str:
    """Which confidence band this field falls into.

    Returns one of 'auto_write', 'review', 'drop'. The bands are defined in
    docs/GUARDRAILS.md and read from settings, not hard-coded here.
    """
    raise NotImplementedError(
        "classify_for_write is implemented in Phase 2 (docs/PHASE_2.md, step 6)"
    )


def min_confidence(extraction: Any) -> float:
    """Lowest confidence across every ExtractedField in the extraction."""
    raise NotImplementedError(
        "min_confidence is implemented in Phase 2 (docs/PHASE_2.md, step 6)"
    )
