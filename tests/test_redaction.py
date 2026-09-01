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
    downstream join depends on it. A labelled NMI must survive redaction."""
    result = RegexRedactor().redact("NMI 6305888444 for the site.")
    assert "6305888444" in result.text
    assert "ACCOUNT_NUMBER" not in result.entity_counts


def test_nmi_repeated_after_its_label_is_still_preserved() -> None:
    """Once labelled, the same NMI appearing later without the label stays intact.
    Otherwise a bill that prints the NMI in a header and again in a table would
    still lose the join key."""
    result = RegexRedactor().redact(
        "NMI 6305888444 for the site. Meter register 6305888444 peak kWh."
    )
    assert result.text.count("6305888444") == 2


def test_unlabelled_digit_run_is_still_an_account_number() -> None:
    """We did not invent an NMI checksum, so an unlabelled 10-digit run is still
    treated as an account number. That is the residual gap, not a regression."""
    result = RegexRedactor().redact("Reference 6305888444 is overdue.")
    assert "6305888444" not in result.text
