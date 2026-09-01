"""The PII redaction boundary.

Owned by: Phase 1. Interface and one working implementation are complete.

This is the trust boundary. Everything that leaves VoltDesk for a third-party API
passes through a Redactor first. The policy - what is redacted, what is reversible -
is in docs/GUARDRAILS.md; this module is the mechanism.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from voltdesk.contracts.common import StrictModel


class RedactionResult(StrictModel):
    """Redacted text plus everything needed to undo it and to audit it."""

    text: str
    entity_counts: dict[str, int]
    #: placeholder token -> original value. Never logged, never persisted, never sent
    #: anywhere. Held in memory only for the lifetime of one request so that the
    #: model's output can be rehydrated before it is written to the CRM.
    reversal_map: dict[str, str]

    @property
    def applied(self) -> bool:
        return bool(self.entity_counts)

    def rehydrate(self, text: str) -> str:
        """Put the real values back into a model response.

        Longest placeholder first, so that PERSON_10 is not corrupted by a
        substitution for PERSON_1.
        """
        for placeholder in sorted(self.reversal_map, key=len, reverse=True):
            text = text.replace(placeholder, self.reversal_map[placeholder])
        return text


class Redactor(ABC):
    """Replace PII with stable placeholders before a third-party call."""

    @abstractmethod
    def redact(self, text: str) -> RedactionResult:
        """Return redacted text. Must be deterministic: the same input yields the
        same placeholders, so that prompt caching is not defeated by redaction."""
        raise NotImplementedError


class NullRedactor(Redactor):
    """Redacts nothing. Only legitimate when VOLTDESK_REDACTION_ENABLED is false,
    which is only legitimate for Tier A corpus material that contains no PII by
    construction. Using this on a customer document is an incident."""

    def redact(self, text: str) -> RedactionResult:
        return RedactionResult(text=text, entity_counts={}, reversal_map={})
