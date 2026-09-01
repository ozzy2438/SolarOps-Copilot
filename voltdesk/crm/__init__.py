"""EspoCRM integration. Client owned by Phase 1; write path owned by Phase 2."""

from voltdesk.crm.client import (
    EXTERNAL_KEY_FIELD,
    CrmAuthError,
    CrmError,
    CrmNotFoundError,
    CrmUnavailableError,
    CrmValidationError,
    EspoCrmClient,
)

__all__ = [
    "EXTERNAL_KEY_FIELD",
    "CrmAuthError",
    "CrmError",
    "CrmNotFoundError",
    "CrmUnavailableError",
    "CrmValidationError",
    "EspoCrmClient",
]
