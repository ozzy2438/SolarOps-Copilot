"""Fabricated identities and structurally realistic tariff templates.

Owned by: Phase 2.

Names, addresses, account numbers and contacts are invented. Tariff *structures*
(flat / time-of-use / demand, with usage + daily-supply + optional demand legs)
are representative of published Victorian small-business electricity plans, not a
copy of a named retailer's standing offer.

docs/DATA_SOURCES.md still has `TODO(verify)` on the public energy-plan API URL
and licence. Until that is resolved we do not commit third-party data; we load
`GeneratorConfig.tariff_source_path` when the file exists and fall back to the
templates below. See ADR-0016.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any

from voltdesk.synthetic.spec import GeneratorConfig, RetailerLayout

FIRST_NAMES = (
    "Jordan",
    "Alex",
    "Sam",
    "Riley",
    "Casey",
    "Morgan",
    "Quinn",
    "Avery",
    "Cameron",
    "Drew",
)
LAST_NAMES = (
    "Hale",
    "Crowe",
    "Perrin",
    "Kerrigan",
    "Bolton",
    "Nash",
    "Farley",
    "Voss",
    "Keene",
    "Daly",
)
STREETS = (
    ("14", "Kerrigan", "Way"),
    ("22", "Perrin", "Court"),
    ("8", "Bolton", "Road"),
    ("105", "Nash", "Street"),
    ("3", "Farley", "Drive"),
    ("41", "Voss", "Place"),
    ("17", "Keene", "Avenue"),
    ("60", "Daly", "Parade"),
    ("9", "Hale", "Terrace"),
    ("28", "Crowe", "Lane"),
)
SUBURBS = (
    ("Dandenong South", "VIC", "3175"),
    ("Truganina", "VIC", "3029"),
    ("Laverton North", "VIC", "3026"),
    ("Campbellfield", "VIC", "3061"),
    ("Somerton", "VIC", "3062"),
    ("Altona North", "VIC", "3025"),
    ("Hallam", "VIC", "3803"),
    ("Epping", "VIC", "3076"),
)
COMPANIES = (
    "Acme Cold Stores",
    "Perrin Packaging",
    "Southgate Logistics",
    "Keene Print Works",
    "Bolton Food Hub",
    "Nash Timber Yard",
    "Voss Auto Parts",
    "Daly Warehousing",
)

# Representative structures only. Not a licensed extract of any named plan.
EMBEDDED_TARIFFS: dict[str, dict[str, Any]] = {
    RetailerLayout.RETAILER_A.value: {
        "name": "Northbeam Energy",
        "flat": {
            "code": "NB-COM-FLAT",
            "usage_c_per_kwh": 22.54,
            "daily_supply_c": 145.20,
        },
        "time_of_use": {
            "code": "NB-COM-TOU",
            "peak_c_per_kwh": 34.18,
            "shoulder_c_per_kwh": 24.10,
            "offpeak_c_per_kwh": 16.82,
            "daily_supply_c": 145.20,
        },
        "demand": {
            "code": "NB-COM-DEMAND",
            "usage_c_per_kwh": 18.40,
            "demand_c_per_kva": 12.50,
            "daily_supply_c": 160.00,
        },
    },
    RetailerLayout.RETAILER_B.value: {
        "name": "Southgrid Retail",
        "flat": {
            "code": "SG-BUS-FLAT",
            "usage_c_per_kwh": 21.10,
            "daily_supply_c": 132.00,
        },
        "time_of_use": {
            "code": "SG-BUS-TOU",
            "peak_c_per_kwh": 31.90,
            "shoulder_c_per_kwh": 22.40,
            "offpeak_c_per_kwh": 15.50,
            "daily_supply_c": 132.00,
        },
        "demand": {
            "code": "SG-BUS-KVA",
            "usage_c_per_kwh": 17.25,
            "demand_c_per_kva": 14.80,
            "daily_supply_c": 155.00,
        },
    },
}


def load_tariffs(config: GeneratorConfig) -> dict[str, dict[str, Any]]:
    """Real file if present and licensed; otherwise the embedded templates."""
    path = Path(config.tariff_source_path)
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) and loaded:
            return loaded
    return EMBEDDED_TARIFFS


def load_interval_totals(
    config: GeneratorConfig, rng: random.Random, days: int
) -> tuple[float, float]:
    """Return (total_kwh, peak_kva) from real interval data, or a shaped profile.

    The physics of the fallback is a weekday-heavy commercial load, not a flat
    random draw. It is still synthetic: we do not invent a licensed dataset.
    """
    path = Path(config.interval_data_path)
    if path.is_file():
        values: list[float] = []
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            for row in reader:
                if not row:
                    continue
                try:
                    values.append(float(row[-1]))
                except ValueError:
                    continue
        if values:
            start = rng.randrange(0, max(1, len(values) - days * 48))
            window = values[start : start + days * 48]
            total = sum(window)
            peak = max(window) * 2.0  # half-hour kWh -> approximate kVA
            return round(total, 1), round(peak, 1)
    return _shaped_load(rng, days)


def _shaped_load(rng: random.Random, days: int) -> tuple[float, float]:
    total = 0.0
    peak_kw = 0.0
    for day in range(days):
        weekend = day % 7 >= 5
        for interval in range(48):
            hour = interval / 2.0
            if weekend:
                base = 18.0
            elif 8.0 <= hour < 17.0:
                base = 85.0
            elif 6.0 <= hour < 8.0 or 17.0 <= hour < 20.0:
                base = 45.0
            else:
                base = 12.0
            kwh = base * 0.5 * (0.92 + rng.random() * 0.16)
            total += kwh
            peak_kw = max(peak_kw, kwh * 2.0)
    return round(total, 1), round(peak_kw / 0.9, 1)


def pick_identity(rng: random.Random) -> dict[str, str]:
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    number, street, kind = rng.choice(STREETS)
    suburb, state, postcode = rng.choice(SUBURBS)
    company = rng.choice(COMPANIES)
    # 10-digit NMI, Victoria-like leading 6. No checksum — TODO(verify) AEMO rule.
    nmi = "6" + "".join(str(rng.randrange(10)) for _ in range(9))
    # 9 digits so an unlabelled run is not 10–11 (the residual NMI/account overlap).
    account = "".join(str(rng.randrange(10)) for _ in range(9))
    return {
        "first": first,
        "last": last,
        "name": f"{first} {last}",
        "company": company,
        "email": f"{first.lower()}.{last.lower()}@example.net",
        "phone": f"04{rng.randrange(10, 99)} {rng.randrange(100, 999)} {rng.randrange(100, 999)}",
        "site_address": f"{number} {street} {kind}, {suburb} {state} {postcode}",
        "nmi": nmi,
        "account_number": account,
        "abn": (
            f"{rng.randrange(10, 99)} {rng.randrange(100, 999)} "
            f"{rng.randrange(100, 999)} {rng.randrange(100, 999)}"
        ),
    }
