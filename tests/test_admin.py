"""Phase 4 operational admin endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from voltdesk.api.app import create_app


def test_start_evaluation_enqueues_verified_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "voltdesk.api.routes.admin._enqueue_evaluation", lambda _model_id: "job-1"
    )

    response = TestClient(create_app()).post(
        "/admin/evaluations", params={"model_id": "gpt-4o-mini"}
    )

    assert response.status_code == 202
    assert response.json() == {
        "job_id": "job-1",
        "model_id": "gpt-4o-mini",
        "status": "queued",
    }


def test_get_evaluation_and_incidents_are_no_longer_stubs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "voltdesk.api.routes.admin._read_evaluation",
        lambda run_id: {"run_id": run_id, "record_count": 150},
    )
    monkeypatch.setattr(
        "voltdesk.api.routes.admin._read_incidents",
        lambda: [{"id": "incident-1", "severity": "medium"}],
    )
    client = TestClient(create_app())

    evaluation = client.get("/admin/evaluations/eval-1")
    incidents = client.get("/admin/incidents")

    assert evaluation.status_code == 200
    assert evaluation.json()["record_count"] == 150
    assert incidents.status_code == 200
    assert incidents.json()["incidents"][0]["id"] == "incident-1"


def test_missing_evaluation_is_a_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voltdesk.api.routes.admin._read_evaluation", lambda _run_id: None)

    response = TestClient(create_app()).get("/admin/evaluations/missing")

    assert response.status_code == 404
