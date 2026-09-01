"""The EspoCRM readiness probe. Owned by Phase 1.

Written after /health/ready reported `espocrm: {"ok": false}` with no reason on a
working stack. The cause was mundane - no API key is configured on a fresh checkout,
so EspoCRM answered 401 - but the probe gave the operator nothing to act on, and the
verdict called a correct fresh install "degraded".
"""

from __future__ import annotations

import httpx
import pytest

from voltdesk.crm.client import EspoCrmClient


def _client(handler: object, api_key: str = "test-key") -> EspoCrmClient:
    return EspoCrmClient(
        base_url="http://crm.test",
        api_key=api_key,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def _never_called(request: httpx.Request) -> httpx.Response:  # pragma: no cover
    raise AssertionError("the probe must not make a request when unconfigured")


def test_no_api_key_reports_unconfigured_not_unreachable() -> None:
    """The state a fresh checkout is actually in. It must be distinguishable from an
    outage, and must not cost a network round trip."""
    with _client(_never_called, api_key="") as crm:
        health = crm.health()
    assert health.configured is False
    assert health.ok is False
    assert "VOLTDESK_ESPOCRM_API_KEY" in health.detail
    assert "espocrm_entities.md" in health.detail


def test_rejected_key_is_reported_as_reachable_but_unauthenticated() -> None:
    """401 means EspoCRM is up and answered. Reporting that as 'down' sends the
    operator to look at the wrong thing."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    with _client(handler) as crm:
        health = crm.health()
    assert health.configured is True
    assert health.reachable is True
    assert health.authenticated is False
    assert health.ok is False
    assert "401" in health.detail


def test_unreachable_instance_is_reported_as_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with _client(handler) as crm:
        health = crm.health()
    assert health.reachable is False
    assert "cannot reach http://crm.test" in health.detail


def test_healthy_instance() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "1", "userName": "voltdesk-api"})

    with _client(handler) as crm:
        health = crm.health()
    assert health.ok is True
    assert health.detail == "ok"


def test_probe_does_not_retry() -> None:
    """The normal _request path retries 3x with backoff on a 30s timeout. In a
    readiness probe that is over a minute of hanging. The probe must make one attempt."""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        raise httpx.ConnectError("connection refused")

    with _client(handler) as crm:
        crm.health()
    assert attempts["n"] == 1


@pytest.mark.parametrize("status_code", [404, 500, 502])
def test_other_errors_are_reported_with_their_status(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="nope")

    with _client(handler) as crm:
        health = crm.health()
    assert health.reachable is True
    assert health.ok is False
    assert str(status_code) in health.detail
