# EspoCRM entities and fields

VoltDesk writes to four custom entities. They must exist in the EspoCRM instance
before any write path works. VoltDesk never touches the CRM database — everything is
created through Administration → Entity Manager, or through EspoCRM's own admin API.

> **`TODO(verify)`** — these definitions were written in Phase 1 without a live
> EspoCRM instance. Phase 2 owns creating them in the instance and correcting this
> file where the instance disagrees. The field *names* below are what
> `voltdesk/contracts/crm.py` serialises, so a correction here is a contract change
> and needs the same care.

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

1. Administration → API Users → create an API user.
2. Authentication method: **API Key**. The key goes in `VOLTDESK_ESPOCRM_API_KEY` and
   is sent as the `X-Api-Key` header.
3. Grant read/write on the four custom entities and read on `Account`. Nothing else —
   VoltDesk has no reason to touch anything it does not write.

**`TODO(verify)`** — confirm against
<https://docs.espocrm.com/development/api/> that API-key authentication and the
bracketed `where[N][...]` search parameters behave as `voltdesk/crm/client.py`
assumes. `tests/test_crm_client.py` pins the current shapes, so any correction shows
up as a visible diff rather than a quiet rewrite.
