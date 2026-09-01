"""Fabricated identities for Tier B documents.

Owned by: Phase 2. Names, addresses, account numbers and contacts are invented.
NMIs are labelled on every bill so redaction preserves the join key (ADR-0009).
The checksum rule is still TODO(verify) and is not enforced.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

_FIRST = (
    "Jordan",
    "Sam",
    "Riley",
    "Alex",
    "Casey",
    "Morgan",
    "Quinn",
    "Avery",
    "Jamie",
    "Taylor",
)
_LAST = (
    "Nguyen",
    "Patel",
    "Rossi",
    "Kowalski",
    "Ibrahim",
    "Chen",
    "Okafor",
    "Silva",
    "Berg",
    "Sato",
)
_STREETS = (
    ("14", "Kerrigan", "Way"),
    ("22", "Perrin", "Court"),
    ("8", "Example", "Street"),
    ("105", "Industrial", "Drive"),
    ("3", "Warehouse", "Road"),
    ("47", "Commerce", "Avenue"),
    ("19", "Freight", "Lane"),
    ("61", "Harbour", "Parade"),
)
_SUBURBS = (
    ("Dandenong South", "VIC", "3175"),
    ("Truganina", "VIC", "3029"),
    ("Laverton North", "VIC", "3026"),
    ("Campbellfield", "VIC", "3061"),
    ("Somerton", "VIC", "3062"),
    ("Scoresby", "VIC", "3179"),
)
_COMPANIES = (
    "Northbeam Energy",
    "Southline Power",
    "Harbourlight Retail",
    "Redgum Electricity",
)
_BUSINESS = (
    "Coldstore Logistics Pty Ltd",
    "Westgate Packing Co",
    "Bayview Plastics",
    "Inner North Joinery",
    "Peninsula Cold Chain",
    "Yarra Parts Wholesale",
)


@dataclass(frozen=True)
class Identity:
    person_name: str
    company_name: str
    email: str
    phone: str
    account_number: str
    nmi: str
    street_no: str
    street_name: str
    street_type: str
    suburb: str
    state: str
    postcode: str
    retailer_name: str

    @property
    def site_address(self) -> str:
        return (
            f"{self.street_no} {self.street_name} {self.street_type}, "
            f"{self.suburb} {self.state} {self.postcode}"
        )


def fabricate(rng: random.Random, *, index: int) -> Identity:
    """Deterministic identity for document `index` given `rng`'s current state."""
    first = rng.choice(_FIRST)
    last = rng.choice(_LAST)
    street = rng.choice(_STREETS)
    suburb = rng.choice(_SUBURBS)
    company = rng.choice(_BUSINESS)
    retailer = rng.choice(_COMPANIES)
    # Victorian NMIs commonly start with 6. Ten digits, no checksum invented.
    nmi = f"6{rng.randint(200000000, 399999999)}"
    account = f"4{rng.randint(100000000, 299999999)}"
    mobile_tail = rng.randint(100000, 999999)
    return Identity(
        person_name=f"{first} {last}",
        company_name=company,
        email=f"{first.lower()}.{last.lower()}{index}@example.test",
        phone=f"0412 {mobile_tail // 1000:03d} {mobile_tail % 1000:03d}",
        account_number=account,
        nmi=nmi,
        street_no=street[0],
        street_name=street[1],
        street_type=street[2],
        suburb=suburb[0],
        state=suburb[1],
        postcode=suburb[2],
        retailer_name=retailer,
    )
