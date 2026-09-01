# Corpus files committed for Phase 2

## `tariffs.json`

- **What:** Victorian Default Offer 2026–27 small-business standing-offer rates
  (GST-inclusive), copied from the Essential Services Commission page.
- **Source URL:** https://www.esc.vic.gov.au/electricity-and-gas/prices-tariffs-and-benchmarks/victorian-default-offer
- **Retrieved:** 2026-09-01
- **Period covered:** 1 July 2026 – 30 June 2027
- **Licence:** `TODO(verify)`. The page footer reads "© 2026 Essential Services
  Commission. All Rights Reserved." Redistribution of this extracted rate table
  inside VoltDesk is not confirmed. Do not treat this file as a licence grant.
  A later phase that publishes or redistributes it must confirm terms.

Demand-tariff *rates* are not in this file. The ESC page states that the price
determination also covers demand structures, but it does not publish a simple
c/kVA table on that page, and Phase 2 will not invent one.

## `interval_data.csv`

- **What:** A constructed half-hourly commercial occupancy shape (weekday vs
  weekend), in kWh per interval. Not a third-party customer dataset.
- **Why it exists:** A licensed public interval dataset was not confirmed before
  this file was committed (`docs/DATA_SOURCES.md` still carries that
  `TODO(verify)`). Inventing a "real" customer file would be worse than an
  honest shape used only to size synthetic bills.
- **Licence:** not applicable — generated in-repo, no third-party content.
- **TODO(verify):** replace with a licence-checked public interval dataset
  (and record attribution) before treating consumption physics as measured
  rather than constructed.
