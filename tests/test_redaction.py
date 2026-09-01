"""PII redaction. Owned by Phase 1.

This is the trust boundary. If these tests are weak, the privacy claim in the README
is false.
"""

from __future__ import annotations

from voltdesk.redaction.regex_redactor import RegexRedactor


def test_email_is_redacted() -> None:
    result = RegexRedactor().redact("Contact jane.doe@example.com about the quote.")
    assert "jane.doe@example.com" not in result.text
    assert result.entity_counts["EMAIL"] == 1
    assert result.applied


def test_account_number_is_redacted() -> None:
    result = RegexRedactor().redact("Account 4029183746 is overdue.")
    assert "4029183746" not in result.text


def test_street_address_is_redacted() -> None:
    result = RegexRedactor().redact("Site at 12 Example Street, deliver there.")
    assert "12 Example Street" not in result.text


def test_repeated_value_gets_one_placeholder() -> None:
    """Same value -> same placeholder, so a repeated account number does not
    produce five placeholders and defeat prompt caching."""
    result = RegexRedactor().redact("a@b.com then a@b.com again and a@b.com")
    assert result.entity_counts["EMAIL"] == 1
    assert result.text.count("[EMAIL_1]") == 3


def test_redaction_is_deterministic() -> None:
    text = "Call 0412 345 678 or email a@b.com about 12 Example Road."
    first = RegexRedactor().redact(text)
    second = RegexRedactor().redact(text)
    assert first.text == second.text


def test_rehydrate_restores_the_original() -> None:
    original = "Email a@b.com and b@c.com."
    result = RegexRedactor().redact(original)
    assert result.rehydrate(result.text) == original


def test_rehydrate_is_not_confused_by_prefix_placeholders() -> None:
    """PERSON_1 must not corrupt PERSON_10. Longest placeholder is substituted first."""
    emails = " ".join(f"user{i}@example.com" for i in range(12))
    result = RegexRedactor().redact(emails)
    assert result.rehydrate(result.text) == emails


def test_nmi_is_deliberately_preserved() -> None:
    """ADR-0009: the NMI is a site identifier, not personal information, and every
    downstream join depends on it. A labelled NMI must survive ACCOUNT_NUMBER."""
    result = RegexRedactor().redact("NMI 6305888444 for the site.")
    assert "6305888444" in result.text
    assert "ACCOUNT_NUMBER" not in result.entity_counts


def test_nmi_with_colon_and_full_label_is_preserved() -> None:
    redactor = RegexRedactor()
    colon = redactor.redact("NMI: 6305888444 billed this quarter.")
    assert "6305888444" in colon.text
    full = redactor.redact(
        "National Metering Identifier 63058884441 appears on the connection."
    )
    assert "63058884441" in full.text
    assert "ABN" not in full.entity_counts


def test_unlabelled_account_number_is_still_redacted() -> None:
    """Over-redaction stays preferred. A 10-digit run that is not labelled as an
    NMI is still an account number."""
    result = RegexRedactor().redact("Account 4029183746 is overdue.")
    assert "4029183746" not in result.text
    assert result.entity_counts["ACCOUNT_NUMBER"] == 1
