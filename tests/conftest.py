"""Shared fixtures.

Owned by: Phase 1.

The whole suite runs with no network, no database and no API keys. A test that needs
one of those is a test that will be skipped in CI and is therefore not a test.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from voltdesk.config import get_settings
from voltdesk.contracts.common import Provenance, Provider, TaskType
from voltdesk.contracts.routing import ModelChoice, RoutingDecision, RoutingStrategy


@pytest.fixture(autouse=True)
def _clean_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """No .env leakage into tests, and a fresh Settings per test."""
    for key in list(os.environ):
        if key.startswith("VOLTDESK_"):
            monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def provenance() -> Provenance:
    return Provenance(
        document_id="doc-1",
        sha256="a" * 64,
        ingested_at=datetime(2026, 3, 1, tzinfo=UTC),
        tier="B",
    )


@pytest.fixture
def routing_decision() -> RoutingDecision:
    return RoutingDecision(
        task_type=TaskType.BILL_EXTRACTION,
        chosen=ModelChoice(provider=Provider.ANTHROPIC, model_id="claude-opus-5"),
        strategy=RoutingStrategy.STATIC_DEFAULT,
        rationale="test fixture",
    )
