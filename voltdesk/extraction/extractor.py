"""Parsed document -> validated extraction contract.

Owned by: Phase 2. See docs/PHASE_2.md.

The extractor calls the model through voltdesk.llm.LLMClient and never through a
provider adapter directly - redaction and the audit record are not optional.
"""

from __future__ import annotations

from voltdesk.contracts.documents import ExtractionResult
from voltdesk.parsers.base import ParsedDocument


class Extractor:
    """Runs one extraction, validates it, and repairs it once if it fails validation."""

    def extract(self, document: ParsedDocument) -> ExtractionResult:
        raise NotImplementedError(
            "Extractor.extract is implemented in Phase 2 (docs/PHASE_2.md, step 4)"
        )
