"""PII redaction. Owned by Phase 1."""

from voltdesk.config import get_settings
from voltdesk.redaction.base import NullRedactor, RedactionResult, Redactor
from voltdesk.redaction.regex_redactor import RegexRedactor


def default_redactor() -> Redactor:
    """The redactor every provider call must use. Honours VOLTDESK_REDACTION_ENABLED."""
    return RegexRedactor() if get_settings().redaction_enabled else NullRedactor()


__all__ = ["NullRedactor", "RedactionResult", "Redactor", "RegexRedactor", "default_redactor"]
