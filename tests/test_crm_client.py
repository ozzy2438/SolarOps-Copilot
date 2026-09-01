"""EspoCRM client. Owned by Phase 1.

Every test runs against a mock transport. These pin the request shapes so that when
Phase 2 verifies them against a live instance, any correction is a visible diff
rather than a quiet rewrite.
"""

from __future__ import annotations

import json

import httpx
import pytest

from voltdesk.crm.client import (
    EXTERNAL_KEY_FIELD,
    CrmAuthError,
    CrmNotFoundError,
    CrmUnavailableError,
    CrmValidationError,
    EspoCrmClient,
)


def _client(handler: object, **kwargs: object) -> EspoCrmClient:
    return EspoCrmClient(
        base_url="http://crm.test",
        api_key="test-key",
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


def test_api_key_is_sent_as_a_header() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"id": "1"})

    with _client(handler) as crm:
        crm.read("EnergyProfile", "1")
    assert seen["x-api-key"] == "test-key"


def test_create_posts_to_the_entity_collection() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "new-1"})

    with _client(handler) as crm:
        crm.create("EnergyProfile", {"name": "x"})

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/EnergyProfile"
    assert captured["body"] == {"name": "x"}


def test_search_encodes_where_clauses_the_way_espocrm_expects() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["query"] = str(request.url.query, "utf-8")
        return httpx.Response(200, json={"total": 0, "list": []})

    with _client(handler) as crm:
        crm.search(
            "EnergyProfile",
            where=[{"type": "equals", "attribute": "nmi", "value": "6123456789"}],
        )

    query = captured["query"]
    assert "where%5B0%5D%5Btype%5D=equals" in query
    assert "where%5B0%5D%5Battribute%5D=nmi" in query


def test_upsert_creates_when_nothing_matches() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "GET":
            return httpx.Response(200, json={"total": 0, "list": []})
        return httpx.Response(200, json={"id": "created"})

    with _client(handler) as crm:
        record, created = crm.upsert("EnergyProfile", "bill:6123456789:a:b", {"name": "x"})

    assert created is True
    assert record["id"] == "created"
    assert calls == ["GET /api/v1/EnergyProfile", "POST /api/v1/EnergyProfile"]


def test_upsert_updates_when_the_external_key_already_exists() -> None:
    """Reprocessing the same document must not create a second CRM record."""
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200, json={"total": 1, "list": [{"id": "existing-1", "name": "old"}]}
            )
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "existing-1"})

    with _client(handler) as crm:
        record, created = crm.upsert("EnergyProfile", "bill:key", {"name": "new"})

    assert created is False
    assert record["id"] == "existing-1"
    assert bodies[0][EXTERNAL_KEY_FIELD] == "bill:key"


def test_duplicate_external_keys_refuse_to_be_resolved_arbitrarily() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"total": 2, "list": [{"id": "a"}, {"id": "b"}]}
        )

    with _client(handler) as crm, pytest.raises(CrmValidationError):
        crm.find_by_external_key("EnergyProfile", "dupe")


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, CrmAuthError),
        (403, CrmAuthError),
        (404, CrmNotFoundError),
        (400, CrmValidationError),
        (409, CrmValidationError),
    ],
)
def test_status_codes_map_to_typed_errors(status: int, expected: type) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="nope")

    with _client(handler) as crm, pytest.raises(expected):
        crm.read("EnergyProfile", "1")


def test_server_errors_are_retried_then_raised() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(503, text="unavailable")

    with _client(handler, max_retries=2) as crm, pytest.raises(CrmUnavailableError):
        crm.read("EnergyProfile", "1")

    assert attempts["n"] == 2


def test_client_errors_are_not_retried() -> None:
    """Retrying a 400 wastes time and hides the real problem."""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(400, text="bad field")

    with _client(handler, max_retries=3) as crm, pytest.raises(CrmValidationError):
        crm.read("EnergyProfile", "1")

    assert attempts["n"] == 1
