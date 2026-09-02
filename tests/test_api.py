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
        ("/admin/incidents", "Phase 4"),
    ],
)
def test_unimplemented_routes_return_501_naming_their_phase(
    client: TestClient, path: str, phase: str
) -> None:
    response = client.get(path)
    assert response.status_code == 501
    assert phase in response.json()["detail"]


def test_review_list_is_no_longer_a_501(client: TestClient) -> None:
    response = client.get("/review")
    assert response.status_code == 200
    assert isinstance(response.json()["items"], list)


def test_qa_abstention_is_a_200(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("voltdesk.api.routes.qa.retrieve", lambda _query: [])

    response = client.post(
        "/qa/ask",
        json={"query_id": "q-out", "question": "Who won the football final?"},
    )

    assert response.status_code == 200
    assert response.json()["abstained"] is True
    assert response.json()["abstention_reason"] == "out_of_scope"


def test_corpus_stats_is_no_longer_a_501(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "voltdesk.api.routes.qa._read_corpus_stats",
        lambda: {
            "documents": 3,
            "chunks": 9,
            "by_source": [
                {"source": "rebate_program_doc", "documents": 3, "chunks": 9}
            ],
        },
    )

    response = client.get("/qa/corpus/stats")

    assert response.status_code == 200
    assert response.json()["documents"] == 3
    assert response.json()["chunks"] == 9


def test_submit_document_returns_202_without_waiting_for_a_model(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "voltdesk.api.routes.documents.enqueue_process_document", lambda _document_id: None
    )
    response = client.post(
        "/documents",
        data={"document_type": "electricity_bill"},
        files={"file": ("bill.txt", b"NMI 6305888444\n", "text/plain")},
    )
    assert response.status_code == 202
    assert "document_id" in response.json()


def test_unconfigured_espocrm_does_not_make_the_service_degraded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase 2: the CRM write path exists, so an unconfigured EspoCRM is a
    readiness failure. The node id is kept so the Phase 2 brief still points here.
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
    response = client.get("/health/ready")
    body = response.json()

    assert "espocrm" in body["unconfigured"]
    assert "espocrm" in body["failing"]
    assert body["status"] == "degraded"
    assert response.status_code == 503
    assert body["checks"]["espocrm"]["configured"] is False
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
