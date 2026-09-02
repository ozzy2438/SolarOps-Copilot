"""Rendered metrics page over audit and evaluation data."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from voltdesk.api.app import create_app


def test_metrics_page_renders_operational_measures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "voltdesk.api.routes.metrics_page._read_snapshot",
        lambda: {
            "calls": 12,
            "cost_usd": 0.42,
            "p95_latency_ms": 1234,
            "redaction_coverage": 0.75,
            "review_queue_depth": 3,
            "outcomes": [{"outcome": "success", "calls": 12}],
            "evaluations": [
                {
                    "model_id": "gpt-4o-mini",
                    "record_count": 150,
                    "exact_match_rate": 0.4,
                    "abstention_rate": 0.3,
                    "p95_latency_ms": 999,
                    "total_cost_usd": 0.2,
                }
            ],
        },
    )

    response = TestClient(create_app()).get("/metrics/page")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "p95 latency" in response.text
    assert "Outcome mix" in response.text
    assert "Review queue depth" in response.text
    assert "gpt-4o-mini" in response.text
