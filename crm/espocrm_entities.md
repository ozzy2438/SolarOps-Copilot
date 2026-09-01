# EspoCRM entities and fields

VoltDesk writes to four custom entities. They must exist in the EspoCRM instance
before any write path works. VoltDesk never touches the CRM database — everything is
created through Administration → Entity Manager, or through EspoCRM's own admin API.

> **Phase 2 live check (EspoCRM 10.0.6, `espocrm/espocrm:latest` on 2026-09-01).**
> Entities and fields below were created through the Administration HTTP actions the
> Entity Manager UI posts (`POST /api/v1/EntityManager/action/createEntity` and
> `POST /api/v1/Admin/fieldManager/{scope}`). Those routes exist in this image; there
> is no separate undocumented “create entity” protocol. An API user with
> `authMethod=ApiKey` was created (`POST /api/v1/User`, `type=api`); the instance
> generated `apiKey` on create, matching https://docs.espocrm.com/development/api/.
>
> Default Entity Manager behaviour prefixes custom entity types with `C`
> (`EnergyProfile` → `CEnergyProfile`). That disagrees with the names in this file
> and in `voltdesk/crm/mapping.py`. Official docs allow
> `customPrefixDisabled` ([Entity Manager](https://docs.espocrm.com/administration/entity-manager/));
> it was set to `true` so the names below exist as written. **At your own risk**, as
> the docs say, if a future Espo core entity collides.
>
> Varchar fields in 10.0.6 have **no Field Manager `unique` parameter**. Uniqueness
> for `voltdeskExternalKey` was added as an entityDefs index
> (`columns: [voltdeskExternalKey, deleted]`, `unique: true`) and rebuild produced
> `UNIQ_VOLTDESK_EXTERNAL_KEY_UNIQUE` in MariaDB. `EspoCrmClient` search
> `where[N][type]=equals` against `voltdeskExternalKey` worked; upsert created then
> updated one row. `voltdesk/crm/client.py` was not changed.
>
> Compose overlay TCP between containers timed out in the Phase 2 environment, so
> the installer was completed with MariaDB + Espo on the host network. That is an
> environment constraint, not a compose-file change. Image tag `latest` is still
> unpinned (`TODO(verify)` remains for a digest pin).

## The idempotency field — on every entity

| Field | Type | Required | Notes |
|---|---|---|---|
| `voltdeskExternalKey` | Varchar (255) | Yes | **Must be unique.** Indexed. |

This is what makes writes idempotent. Reprocessing the same document must update one
record, not create a second. `EspoCrmClient.find_by_external_key` **refuses** when it
finds two records sharing a key, rather than picking one — so if the uniqueness
constraint is missing in the instance, VoltDesk fails loudly instead of corrupting
data quietly.

Key derivation (`voltdesk/crm/mapping.py`):

- `EnergyProfile` → `bill:{nmi}:{period_start}:{period_end}`
- `SiteAssessment` → `site:{sha256(normalised_address)[:16]}:{assessed_on}`

Derived from facts on the document, never from a UUID we generated.

Also on every entity:

| Field | Type | Notes |
|---|---|---|
| `voltdeskSourceDocumentId` | Varchar (64) | `app.documents.id` of the source |
| `voltdeskExtractionConfidence` | Float | Minimum confidence across the fields that populated the record |

`voltdeskExtractionConfidence` is what lets a CRM user see that a record was written
by a machine and how sure it was. Without it, an auto-written record is
indistinguishable from one a person typed.

---

## `EnergyProfile`

One per bill, per site. The consumption picture a system is sized against.

| Field | Type | Required | From (`ExtractedBill`) |
|---|---|---|---|
| `name` | Varchar (255) | Yes | Derived: `"{nmi} {period_start}–{period_end}"` |
| `nmi` | Varchar (11) | Yes | `nmi` |
| `retailerName` | Varchar (255) | No | `retailer_name` |
| `billingPeriodStart` | Date | Yes | `billing_period.start` |
| `billingPeriodEnd` | Date | Yes | `billing_period.end` |
| `totalConsumptionKwh` | Float | Yes | `total_consumption_kwh` |
| `peakDemandKva` | Float | No | `peak_demand_kva` |
| `totalAmountAud` | Currency (AUD) | Yes | `total_amount.amount` |
| `tariffType` | Enum | Yes | `tariff_type` — `flat`, `time_of_use`, `demand`, `unknown` |
| `tariffCode` | Varchar (64) | No | `tariff_code` |
| `solarExportKwh` | Float | No | `solar_export_kwh` |

**Not written:** `account_number` (PII, no CRM use), `components` (belongs in
`app.extractions`, not the CRM), `parser_warnings` (operational detail).

---

## `SiteAssessment`

| Field | Type | Required | From (`ExtractedSiteAssessment`) |
|---|---|---|---|
| `name` | Varchar (255) | Yes | Derived: `"{site_address} – {assessed_on}"` |
| `siteAddress` | Varchar (255) | Yes | `site_address` |
| `nmi` | Varchar (11) | No | `nmi` |
| `assessedOn` | Date | No | `assessed_on` |
| `roofMaterial` | Varchar (128) | No | `roof_material` |
| `usableRoofAreaM2` | Float | No | Sum of `roof_planes[].usable_area_m2` |
| `phaseConfiguration` | Enum | No | `single_phase`, `three_phase`, `unknown` |
| `mainSwitchRatingA` | Float | No | `main_switch_rating_a` |
| `existingPvKw` | Float | No | `existing_pv_kw` |
| `batterySpaceAvailable` | Bool | No | `battery_space_available` |
| `hazards` | Text | No | Newline-joined `hazards[]` |
| `accessConstraints` | Text | No | `access_constraints` |

**Not written:** `assessor_name` (staff PII — the CRM already knows who owns the
record), `roof_planes` detail beyond the area sum, `parser_warnings`.

---

## `GridConnection`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | Varchar (255) | Yes | Derived from NMI |
| `nmi` | Varchar (11) | Yes | |
| `dnspName` | Varchar (128) | No | **`TODO(verify)`** — NMI-to-DNSP mapping is published per jurisdiction. Phase 3 must source it, not infer it from a postcode. |
| `exportLimitKw` | Float | No | |
| `connectionStatus` | Enum | No | `not_applied`, `applied`, `approved`, `rejected` |
| `applicationReference` | Varchar (64) | No | |

---

## `Proposal`

VoltDesk populates the technical fields only. Generating customer-facing proposal
documents is permanently out of scope (`docs/SCOPE.md`).

| Field | Type | Required |
|---|---|---|
| `name` | Varchar (255) | Yes |
| `siteAddress` | Varchar (255) | Yes |
| `proposedPvKw` | Float | No |
| `proposedBatteryKwh` | Float | No |
| `estimatedAnnualSavingsAud` | Currency (AUD) | No |
| `status` | Enum | No |

---

## Relationships

| From | To | Type |
|---|---|---|
| `Account` | `SiteAssessment` | One-to-many |
| `Account` | `EnergyProfile` | One-to-many |
| `SiteAssessment` | `GridConnection` | One-to-one |
| `SiteAssessment` | `Proposal` | One-to-many |

`Account` is EspoCRM's built-in entity. VoltDesk does not create or modify Accounts —
linking an extracted record to the right Account is a human decision, and getting it
wrong silently attaches one customer's bill to another customer.

## API user setup

Until this is done, `/health/ready` reports
`espocrm: {"configured": false, ...}` and lists it under `unconfigured`. That is the
expected state of a fresh checkout, not a fault — VoltDesk cannot create an EspoCRM API
user for itself.

1. Open EspoCRM (http://localhost:8080 by default) and complete its installer if this is
   the first boot. The container needs a minute or two before it answers.
2. Log in as admin, then Administration → API Users → create an API user.
3. Authentication method: **API Key**. Copy the generated key into
   `VOLTDESK_ESPOCRM_API_KEY` in `.env`; it is sent as the `X-Api-Key` header.
4. Grant read/write on the four custom entities and read on `Account`. Nothing else —
   VoltDesk has no reason to touch anything it does not write.
5. Create the custom entities and fields described above (Administration → Entity
   Manager). The API user's payloads will be rejected with `CrmValidationError` until
   they exist.
6. `docker compose up -d api` to pick up the new key, then confirm:

   ```bash
   curl -s localhost:8000/health/ready | jq '.checks.espocrm'
   ```

   Expected once it is working: `{"ok": true, "configured": true, "reachable": true,
   "detail": "ok"}`.

   The `detail` field tells you which step is still missing:

   | detail says | What to fix |
   |---|---|
   | `no API key configured` | Step 3 — the key is not in `.env`, or the API container did not pick it up |
   | `answered 401` / `403` | The key is wrong, the API user is inactive, or its ACL denies access |
   | `cannot reach ...` | EspoCRM is not running, or `VOLTDESK_ESPOCRM_BASE_URL` is wrong (inside Compose it must be `http://espocrm`, not `localhost`) |
   | `answered 404` | Reachable, but the path was rejected — check the instance is fully installed |

**`TODO(verify)`** — confirm against
<https://docs.espocrm.com/development/api/> that API-key authentication and the
bracketed `where[N][...]` search parameters behave as `voltdesk/crm/client.py`
assumes. `tests/test_crm_client.py` pins the current shapes, so any correction shows
up as a visible diff rather than a quiet rewrite.
