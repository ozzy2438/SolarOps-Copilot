# Data sources

Two tiers. The distinction is a deliberate engineering and privacy decision and must
survive to the final documentation — it is the answer to "is any of this real
customer data?" and the answer must be *no*.

## Tier A — real, publicly sourced

Used for the retrieval corpus and reference tables. Never contains personal
information.

| Source | Used for | Status |
|---|---|---|
| Clean Energy Council approved module list | Reference table; component validation | URL verified 2026-09-01: https://cleanenergycouncil.org.au/industry-programs/products-program/modules. **Not ingested.** CEC says approved-product data is available to third parties only under a separately granted data licence; VoltDesk has no such grant. `TODO(verify)` remains: obtain a licence from `data@cleanenergycouncil.org.au`. |
| Clean Energy Council approved inverter list | Reference table; component validation | URL verified 2026-09-01: https://cleanenergycouncil.org.au/industry-programs/products-program/inverters. **Not ingested.** Same separate-data-licence requirement as the module list; VoltDesk has no grant. `TODO(verify)` remains. |
| Manufacturer technical datasheets | Corpus; the real parsing test bed (real PDFs, real table layouts) | Fronius Symo Advanced 20.0-3-M page verified 2026-09-01: https://www.fronius.com/en-au/australia/solar-energy/installers-partners/technical-data/all-products/inverters/fronius-symo-advanced/symo-advanced-20-0-3-m. **Not ingested.** Fronius Australia terms reserve copyright in technical documents and grant use only for the intended purpose; no redistribution/embedding grant was found. `TODO(verify)` remains per manufacturer. |
| Distribution network embedded generation connection guidelines | Corpus; export limits, connection requirements | Energex document library and current `STNW1170 Standard for Small IES Connections` (dated 2025-02-21) verified 2026-09-01: https://www.energex.com.au/contractors/document-library. **Not ingested.** Energy Queensland terms prohibit use of group intellectual property without written agreement and do not grant corpus redistribution. AusNet terms independently prohibit copying and automated extraction. `TODO(verify)` remains per DNSP. |
| Regulator small-scale certificate methodology | Corpus; certificate calculations | Clean Energy Regulator `Create small-scale technology certificates` page verified and retrieved 2026-09-01: https://cer.gov.au/schemes/renewable-energy-target/small-scale-renewable-energy-scheme/small-scale-technology-certificates/create-small-scale-technology-certificates. Website text is CC BY 4.0 except identified third-party material, logos and the Coat of Arms: https://cer.gov.au/about-us/our-policies/copyright. An attributed, adapted text snapshot is ingested. |
| State and federal rebate program documentation | Corpus; eligibility questions | Federal `Cheaper Home Batteries Program` page (https://www.energy.gov.au/rebates/cheaper-home-batteries-program) and Victorian `Notice to Market 2026-27, section 3` (https://www.solar.vic.gov.au/notice-to-market-2026-27/section-3-requirements-solar-pv-rebates) verified and retrieved 2026-09-01. Both sites license their own text under CC BY 4.0; third-party content, branding and government arms are excluded. Attributed, adapted text snapshots are ingested. |
| Public energy plan / tariff API data | Synthetic bill generation (real tariff structures) | Phase 2 used the Essential Services Commission Victorian Default Offer 2026–27 small-business standing-offer tables (retrieved 2026-09-01 from https://www.esc.vic.gov.au/electricity-and-gas/prices-tariffs-and-benchmarks/victorian-default-offer). Rates are in `data/corpus/tariffs.json`. **Licence still `TODO(verify)`** — the page is All Rights Reserved. |
| Public half-hourly consumption and PV generation interval datasets | Synthetic bill generation (real consumption physics) | Phase 2 did **not** commit a third-party interval file. `data/corpus/interval_data.csv` is an in-repo occupancy shape (see `data/corpus/SOURCES.md`). **`TODO(verify)`** a licence-checked public dataset remains open. |

**Tier A rows above:** Phase 1 left every URL and licence as `TODO(verify)`. Phase 2 recorded a source URL and retrieval date for the VDO tariff tables used by the synthetic generator, and recorded that interval data is an in-repo occupancy shape rather than a third-party file. Phase 3 verified all six retrieval-corpus rows on 2026-09-01. Three government sources have an applicable CC BY 4.0 grant and are eligible for ingestion. The CEC lists, manufacturer datasheet and DNSP guideline remain excluded until the rights holder grants suitable reuse terms. Phase 2's VDO and public-interval licence TODOs remain open because they are not Phase 3 retrieval-corpus inputs.

### NMI-to-DNSP reference

Phase 3 verified the authoritative reference on 2026-09-01 without adding a postcode
inference. AEMO lists `MSATS National Metering Identifier Procedure v7.4` (effective
2026-05-31) and `National Metering Allocation List v14` as the current documents at
https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/market-operations/retail-and-metering/metering-procedures-guidelines-and-processes.
The allocation list maps NMI blocks to network service providers. AEMO's legal notice
allows personal use or separately authorised use only, so neither document is ingested
or redistributed here. Runtime DNSP derivation is not added: the existing contracts
carry a DNSP value supplied by an authoritative business source, and guessing from a
postcode remains prohibited.

### The rule for ingestion

`vec.corpus_documents.licence` is nullable in the schema, but a NULL there means the
document had no verified licence **and should not have been ingested**. Phase 3 owns
this check. Ingesting material VoltDesk has no right to redistribute is the one
failure in this project that a later phase cannot fix.

Record, per corpus document: source URL, licence, and retrieval date. The retrieval
date matters — rebate programs and connection guidelines are revised, and an answer
cited from a superseded version is wrong in a way that looks right.

## Tier B — synthetic

Only where personally identifiable information would otherwise appear:

- Customer and lead records
- Site assessment notes
- Email threads
- Electricity bill PDFs

### The rule

> Names, addresses, account numbers and contact details are fabricated.
> **The physics and the pricing are not.**

A synthetic bill with invented tariff rates teaches the parser nothing and makes the
extraction benchmark meaningless. Synthetic documents are built on top of real tariff
structures and real interval data from Tier A.

### Deliberate defects

The generator injects these on purpose (`voltdesk/synthetic/spec.py`). A corpus of
clean documents produces a parser that fails on the first real one.

- Skewed scans
- Missing text layer (forces the OCR path)
- Multi-page bills where a tariff table splits across a page break
- Inconsistent date formats — `DD/MM/YYYY` and `D Mon YYYY` in the same corpus
- Missing fields
- Two retailer layouts, so extraction cannot overfit to one template
- Handwritten-looking site notes
- Quoted email history (the trap that makes naive parsing scale quadratically)
- Low-contrast photocopies

### Reproducibility

`GeneratorConfig(seed=N)` fully determines the output. Same seed, same config, same
documents byte for byte. This is what makes the golden set reproducible and is why
ground truth for synthetic records carries `ground_truth_source='generator_seed'` —
the generator already knows every answer it constructed.

## What is never done

- Real customer documents are never committed to this repository.
- Real customer documents are never ingested into the retrieval corpus. The corpus is
  Tier A only, which is what makes it structurally impossible for a Q&A answer to leak
  one customer's data to another user.
- A synthetic record is never reported as real. `app.documents.tier` is a column, not
  a naming convention, precisely so this cannot happen by accident.
