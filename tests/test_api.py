"""HTTP surface. Owned by Phase 1.

Phase 1's promise about the API is narrow and worth pinning: every route the
finished system will expose is registered, and an unimplemented one says 501 with
the phase that owns it - never 404.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from voltdesk.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


def test_liveness_touches_no_dependency(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_is_a_complete_map_of_the_service(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for expected in [
        "/health/live",
        "/health/ready",
        "/metrics",
        "/documents",
        "/documents/{document_id}",
        "/documents/{document_id}/extraction",
        "/documents/{document_id}/write-to-crm",
        "/qa/ask",
        "/qa/corpus/stats",
        "/review",
        "/review/{review_id}",
        "/review/{review_id}/resolve",
        "/admin/evaluations",
        "/admin/incidents",
    ]:
        assert expected in paths, f"{expected} is not registered"


@pytest.mark.parametrize(
    ("path", "phase"),
    [
        ("/documents/abc", "Phase 2"),
        ("/qa/corpus/stats", "Phase 3"),
        ("/review", "Phase 2"),
        ("/admin/incidents", "Phase 4"),
    ],
)
def test_unimplemented_routes_return_501_naming_their_phase(
    client: TestClient, path: str, phase: str
) -> None:
    response = client.get(path)
    assert response.status_code == 501
    assert phase in response.json()["detail"]


def test_unconfigured_espocrm_does_not_make_the_service_degraded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh checkout has no EspoCRM API key, because an API user has to be created
    by hand. Reporting that correct state as 503 trains people to ignore this endpoint.

    The dependency is still reported in full, and listed under `unconfigured`, so it
    cannot be missed - it just does not decide the verdict.
    """
    from voltdesk.api.routes import health as health_route

    class _Health:
        configured = False
        reachable = False
        authenticated = False
        detail = "no API key configured (VOLTDESK_ESPOCRM_API_KEY is empty)."
        ok = False

    class _Crm:
        def __enter__(self) -> _Crm:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def health(self) -> _Health:
            return _Health()

    monkeypatch.setattr(health_route, "EspoCrmClient", _Crm)
    body = client.get("/health/ready").json()

    assert "espocrm" in body["unconfigured"]
    assert "espocrm" not in body["failing"]
    assert body["checks"]["espocrm"]["configured"] is False
    # The reason must be there. A bare ok:false gives the operator nothing to act on.
    assert body["checks"]["espocrm"]["detail"]


def test_configured_but_failing_espocrm_is_a_real_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other side of the rule: a dependency someone HAS configured and which is
    down must still produce 503."""
    from voltdesk.api.routes import health as health_route

    class _Health:
        configured = True
        reachable = False
        authenticated = False
        detail = "cannot reach http://espocrm: connection refused"
        ok = False

    class _Crm:
        def __enter__(self) -> _Crm:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def health(self) -> _Health:
            return _Health()

    monkeypatch.setattr(health_route, "EspoCrmClient", _Crm)
    response = client.get("/health/ready")
    body = response.json()

    assert "espocrm" in body["failing"]
    assert body["status"] == "degraded"
    assert response.status_code == 503
