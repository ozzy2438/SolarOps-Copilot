"""Deterministic pattern-based PII redaction.

Owned by: Phase 1. Fully implemented and the default.

Deliberately conservative and boring. It over-redacts rather than under-redacts:
a redacted street number costs an extraction a little accuracy, an un-redacted
customer address that reaches a third party is a privacy incident.

Known limitation, recorded rather than hidden: this catches patterned identifiers,
not free-form personal names. A name that appears without an email or phone next to
it will pass through. Phase 2 must not assume otherwise; docs/GUARDRAILS.md states
the mitigation (synthetic names in Tier B, so the names that pass through are
fabricated by construction).
"""

from __future__ import annotations

import re

from voltdesk.redaction.base import RedactionResult, Redactor

#: (entity type, compiled pattern). Order matters: more specific patterns first, so
#: that an email is not partially consumed by the phone-number pattern.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")),
    # Australian mobile and landline, with or without +61, spaces or hyphens.
    ("PHONE", re.compile(r"(?:\+?61[ -]?|\b0)[2-9](?:[ -]?\d){8}\b")),
    # Australian Business Number: 11 digits, commonly spaced 2-3-3-3.
    ("ABN", re.compile(r"\b\d{2}[ ]?\d{3}[ ]?\d{3}[ ]?\d{3}\b")),
    # Retailer account numbers: long digit runs that are not an ABN.
    ("ACCOUNT_NUMBER", re.compile(r"\b\d{8,12}\b")),
    ("BSB", re.compile(r"\b\d{3}-\d{3}\b")),
    # Street address line: number + words + street-type suffix.
    (
        "STREET_ADDRESS",
        re.compile(
            r"\b\d+[A-Za-z]?(?:[/-]\d+[A-Za-z]?)?\s+[\w' ]{2,40}?\s+"
            r"(?:St|Street|Rd|Road|Ave|Avenue|Dr|Drive|Ct|Court|Pl|Place|Ln|Lane|"
            r"Hwy|Highway|Pde|Parade|Cres|Crescent|Tce|Terrace|Way|Blvd|Boulevard)\b\.?",
            re.IGNORECASE,
        ),
    ),
]

#: The NMI is a site identifier, not a person, and every downstream join depends on
#: it. It is deliberately NOT redacted. This is a decision, recorded in ADR-0009.
NEVER_REDACTED_NOTE = "NMI is a site identifier and is intentionally preserved. See ADR-0009."


class RegexRedactor(Redactor):
    """Pattern-based redactor. Deterministic for a given input string."""

    def redact(self, text: str) -> RedactionResult:
        counts: dict[str, int] = {}
        reversal: dict[str, str] = {}
        # Same original value -> same placeholder, so a bill that repeats an account
        # number 5 times produces one placeholder, and the prompt stays cacheable.
        seen: dict[tuple[str, str], str] = {}

        for entity_type, pattern in _PATTERNS:

            def _replace(match: re.Match[str], _t: str = entity_type) -> str:
                original = match.group(0)
                key = (_t, original)
                if key in seen:
                    return seen[key]
                counts[_t] = counts.get(_t, 0) + 1
                placeholder = f"[{_t}_{counts[_t]}]"
                seen[key] = placeholder
                reversal[placeholder] = original
                return placeholder

            text = pattern.sub(_replace, text)

        return RedactionResult(text=text, entity_counts=counts, reversal_map=reversal)
