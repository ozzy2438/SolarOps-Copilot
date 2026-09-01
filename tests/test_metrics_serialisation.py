"""The metrics endpoint must return numbers, not Decimals-as-strings.

Owned by: Phase 1.

Found by running the endpoint against a real PostgreSQL: NUMERIC columns arrive as
`Decimal`, which FastAPI serialises to a JSON *string* — and an averaged zero becomes
the string "0E-20". Phase 4 builds the metrics page on this endpoint, and no chart can
plot "0E-20". This test pins the coercion so the bug cannot come back.
"""

from __future__ import annotations

from decimal import Decimal

from voltdesk.api.routes.metrics import _jsonable


def test_decimal_becomes_float() -> None:
    assert _jsonable(Decimal("0.014500")) == 0.0145
    assert isinstance(_jsonable(Decimal("0.014500")), float)


def test_averaged_zero_does_not_become_scientific_notation() -> None:
    """PostgreSQL AVG over zeros returns Decimal('0E-20'), whose str() is "0E-20"."""
    value = _jsonable(Decimal("0E-20"))
    assert value == 0.0
    assert isinstance(value, float)


def test_non_decimal_values_pass_through_untouched() -> None:
    for value in (1, "bill_extraction", None, 2.5, True):
        assert _jsonable(value) is value


def test_empty_window_reports_zero_not_null() -> None:
    """SUM over zero rows is NULL in SQL while COUNT is 0.

    Found by hitting /metrics against a freshly migrated, empty database: it reported
    `calls: 0` alongside `redacted_calls: null`, and anything computing a redaction
    coverage ratio from that pair divides by null. Every SUM in the metrics queries is
    now COALESCE'd; this test pins that the SQL text keeps them.
    """
    from voltdesk.api.routes.metrics import _REDACTION, _SUMMARY

    redaction_sql = str(_REDACTION)
    assert "COALESCE(SUM(CASE WHEN redaction_applied" in redaction_sql, (
        "redacted_calls must be COALESCE'd or an empty window reports null"
    )

    summary_sql = str(_SUMMARY)
    for column in ("cost_usd", "input_tokens", "output_tokens"):
        assert f"COALESCE(SUM({column})" in summary_sql, (
            f"{column} must be COALESCE'd or an empty group reports null"
        )
