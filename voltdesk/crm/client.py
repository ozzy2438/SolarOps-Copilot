"""EspoCRM REST client.

Owned by: Phase 1. Fully implemented, because every later phase writes through it
and none of them should have to modify it.

VoltDesk is a separate service. It never touches the EspoCRM database. Everything
goes through this client.

TODO(verify): the request shapes below follow EspoCRM's documented REST API
(https://docs.espocrm.com/development/api/ - CRUD, search parameters, and API-user
key authentication). They were not exercised against a live instance during Phase 1.
Phase 2 owns confirming them and correcting this file if the instance disagrees;
`tests/test_crm_client.py` pins the current shapes so a correction is a visible diff.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import httpx

from voltdesk.config import get_settings
from voltdesk.contracts.common import StrictModel
from voltdesk.logging_setup import get_logger

logger = get_logger(__name__)

#: EspoCRM custom field used as VoltDesk's idempotency key on every entity.
#: Defined in crm/espocrm_entities.md; must exist in the instance.
EXTERNAL_KEY_FIELD = "voltdeskExternalKey"


class CrmHealth(StrictModel):
    """What a readiness probe found. Three separate facts, because they have three
    different fixes and a single boolean told the operator none of them."""

    configured: bool
    reachable: bool
    authenticated: bool
    detail: str

    @property
    def ok(self) -> bool:
        return self.configured and self.reachable and self.authenticated


class CrmError(RuntimeError):
    """Base for every CRM failure. Carries the status code when there was one."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CrmAuthError(CrmError):
    """401/403. Retrying will not help; the API key or the user's ACL is wrong."""


class CrmNotFoundError(CrmError):
    """404 on a record that was expected to exist."""


class CrmValidationError(CrmError):
    """400/409. The payload is wrong - usually a custom field that does not exist
    in the instance. Retrying will not help; fix crm/espocrm_entities.md."""


class CrmUnavailableError(CrmError):
    """5xx or a connection failure. Retryable."""


class EspoCrmClient:
    """Synchronous EspoCRM client: auth, CRUD, search, idempotent upsert, retries."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 3,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.espocrm_base_url).rstrip("/")
        self._api_key = (
            api_key if api_key is not None else settings.espocrm_api_key.get_secret_value()
        )
        self._timeout = timeout if timeout is not None else settings.espocrm_timeout_seconds
        self._max_retries = max_retries
        # `transport` is injectable so tests can mount a mock without monkeypatching.
        self._client = httpx.Client(
            base_url=f"{self._base_url}/api/v1",
            timeout=self._timeout,
            transport=transport,
            headers={
                "X-Api-Key": self._api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> EspoCrmClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ---- HTTP ------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """One request with bounded exponential backoff on retryable failures."""
        last_error: CrmError | None = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.request(method, path, params=params, json=json_body)
            except httpx.TimeoutException as exc:
                last_error = CrmUnavailableError(f"espocrm timeout on {method} {path}: {exc}")
            except httpx.TransportError as exc:
                last_error = CrmUnavailableError(f"espocrm unreachable on {method} {path}: {exc}")
            else:
                error = self._classify(response, method, path)
                if error is None:
                    if response.status_code == 204 or not response.content:
                        return None
                    return response.json()
                if not isinstance(error, CrmUnavailableError):
                    raise error
                last_error = error

            if attempt < self._max_retries - 1:
                time.sleep(2**attempt)

        assert last_error is not None
        raise last_error

    @staticmethod
    def _classify(response: httpx.Response, method: str, path: str) -> CrmError | None:
        """Map a status code to a typed error, or None when the response is good."""
        status = response.status_code
        if status < 400:
            return None
        # EspoCRM puts a human-readable reason in this header on validation failures.
        reason = response.headers.get("X-Status-Reason", "")
        detail = f"{method} {path} -> {status} {reason} {response.text[:300]}".strip()
        if status in (401, 403):
            return CrmAuthError(detail, status_code=status)
        if status == 404:
            return CrmNotFoundError(detail, status_code=status)
        if status in (400, 409, 422):
            return CrmValidationError(detail, status_code=status)
        return CrmUnavailableError(detail, status_code=status)

    # ---- CRUD ------------------------------------------------------------

    def create(self, entity_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /api/v1/{EntityType}. Returns the created record."""
        result = self._request("POST", f"/{quote(entity_type)}", json_body=payload)
        return dict(result or {})

    def read(self, entity_type: str, record_id: str) -> dict[str, Any]:
        result = self._request("GET", f"/{quote(entity_type)}/{quote(record_id)}")
        return dict(result or {})

    def update(self, entity_type: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """PUT /api/v1/{EntityType}/{id}. EspoCRM treats PUT as a partial update."""
        result = self._request(
            "PUT", f"/{quote(entity_type)}/{quote(record_id)}", json_body=payload
        )
        return dict(result or {})

    def delete(self, entity_type: str, record_id: str) -> None:
        self._request("DELETE", f"/{quote(entity_type)}/{quote(record_id)}")

    def search(
        self,
        entity_type: str,
        *,
        where: list[dict[str, Any]] | None = None,
        max_size: int = 20,
        offset: int = 0,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        """GET /api/v1/{EntityType} with EspoCRM's bracketed `where` parameters.

        `where` entries look like {"type": "equals", "attribute": "name", "value": "x"}.
        """
        params: dict[str, Any] = {"maxSize": max_size, "offset": offset}
        if order_by:
            params["orderBy"] = order_by
        for index, clause in enumerate(where or []):
            for key, value in clause.items():
                params[f"where[{index}][{key}]"] = value
        result = self._request("GET", f"/{quote(entity_type)}", params=params)
        return list((result or {}).get("list", []))

    # ---- Idempotent upsert ----------------------------------------------

    def find_by_external_key(self, entity_type: str, external_key: str) -> dict[str, Any] | None:
        """The lookup that makes writes idempotent."""
        matches = self.search(
            entity_type,
            where=[
                {"type": "equals", "attribute": EXTERNAL_KEY_FIELD, "value": external_key}
            ],
            max_size=2,
        )
        if not matches:
            return None
        if len(matches) > 1:
            # Two records sharing an external key means the uniqueness constraint in
            # the instance is missing. Refuse rather than pick one arbitrarily.
            raise CrmValidationError(
                f"{entity_type} has {len(matches)} records with "
                f"{EXTERNAL_KEY_FIELD}={external_key!r}; the field must be unique. "
                f"See crm/espocrm_entities.md."
            )
        return dict(matches[0])

    def upsert(
        self, entity_type: str, external_key: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]:
        """Create or update by external key. Returns (record, created).

        Reprocessing the same document must not create a second CRM record. That is
        the whole reason the external key exists.
        """
        body = {**payload, EXTERNAL_KEY_FIELD: external_key}
        existing = self.find_by_external_key(entity_type, external_key)
        if existing is None:
            logger.info("crm_create", entity_type=entity_type, external_key=external_key)
            return self.create(entity_type, body), True

        record_id = existing["id"]
        logger.info(
            "crm_update", entity_type=entity_type, external_key=external_key, record_id=record_id
        )
        return self.update(entity_type, record_id, body), False

    def is_configured(self) -> bool:
        """False when no API key is set. That is a configuration state, not an outage:
        an EspoCRM API user has to be created by hand (crm/espocrm_entities.md), so a
        fresh checkout legitimately has no key yet."""
        return bool(self._api_key)

    def health(self, timeout: float = 3.0) -> CrmHealth:
        """Bounded readiness probe. Never raises, never retries.

        Deliberately does NOT go through `_request`. That path retries three times with
        exponential backoff on a 30s timeout, so an unreachable CRM would block
        /health/ready for over a minute - useless in a readiness probe, which has to
        answer while someone is still looking at it.

        Distinguishes three states that a bare boolean collapsed into one:
        unconfigured, unreachable, and reachable-but-rejected. They have different
        fixes, so the probe has to name which one it found.
        """
        if not self.is_configured():
            return CrmHealth(
                configured=False,
                reachable=False,
                authenticated=False,
                detail=(
                    "no API key configured (VOLTDESK_ESPOCRM_API_KEY is empty). Create "
                    "an EspoCRM API user and set the key - see crm/espocrm_entities.md. "
                    "Until then the CRM write path is unavailable."
                ),
            )

        try:
            response = self._client.request("GET", "/App/user", timeout=timeout)
        except httpx.TimeoutException:
            return CrmHealth(
                configured=True,
                reachable=False,
                authenticated=False,
                detail=f"no response from {self._base_url} within {timeout:g}s",
            )
        except httpx.TransportError as exc:
            return CrmHealth(
                configured=True,
                reachable=False,
                authenticated=False,
                detail=f"cannot reach {self._base_url}: {exc}",
            )

        if response.status_code in (401, 403):
            return CrmHealth(
                configured=True,
                reachable=True,
                authenticated=False,
                detail=(
                    f"EspoCRM answered {response.status_code}: it is running, but it "
                    f"rejected the API key. Check the API user exists and is active, "
                    f"and that its ACL grants access."
                ),
            )
        if response.status_code >= 400:
            return CrmHealth(
                configured=True,
                reachable=True,
                authenticated=False,
                detail=(
                    f"EspoCRM answered {response.status_code} to GET /api/v1/App/user. "
                    f"The instance is reachable but did not accept the request."
                ),
            )

        return CrmHealth(
            configured=True, reachable=True, authenticated=True, detail="ok"
        )
