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
