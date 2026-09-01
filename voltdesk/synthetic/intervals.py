"""Constructed half-hourly occupancy shape for synthetic bills.

Owned by: Phase 2. This is not a third-party customer dataset; see
data/corpus/SOURCES.md. If interval_data.csv is present it is used as-is.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

from voltdesk.synthetic.spec import GeneratorConfig

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HEADER = ("timestamp", "site_id", "consumption_kwh", "generation_kwh")


def occupancy_kwh(weekday: bool, interval: int) -> tuple[float, float]:
    """kWh for one 30-minute slot. `interval` is 0..47 starting at local midnight.

    Weekday commercial occupancy is high 09:00-17:00, which lines up with the
    VDO small-business peak window (9am-9pm weekdays). Weekend is a low base.
    """
    hour = interval / 2
    if weekday:
        if 9 <= hour < 17:
            load = 18.0
        elif 7 <= hour < 9 or 17 <= hour < 21:
            load = 8.0
        else:
            load = 2.5
        gen = 3.4 if 10 <= hour < 16 else 0.0
    else:
        load = 3.0 if 9 <= hour < 17 else 1.6
        gen = 2.8 if 10 <= hour < 16 else 0.0
    return load, gen


def default_rows() -> list[tuple[str, str, str, str]]:
    """Two sites, 14 days from 2026-01-05 (a Monday), 48 intervals/day."""
    start = datetime(2026, 1, 5, tzinfo=UTC)
    rows: list[tuple[str, str, str, str]] = []
    for site in ("shape-a", "shape-b"):
        scale = 1.0 if site == "shape-a" else 0.7
        for day in range(14):
            moment = start + timedelta(days=day)
            weekday = moment.weekday() < 5
            for interval in range(48):
                stamp = moment + timedelta(minutes=30 * interval)
                load, gen = occupancy_kwh(weekday, interval)
                rows.append(
                    (
                        stamp.isoformat(),
                        site,
                        f"{load * scale:.3f}",
                        f"{gen * scale:.3f}",
                    )
                )
    return rows


def load_intervals(config: GeneratorConfig) -> list[tuple[str, str, float, float]]:
    path = Path(config.interval_data_path)
    if not path.is_absolute():
        path = _REPO_ROOT / path
    if not path.is_file():
        raw = default_rows()
    else:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader)
            if tuple(header) != _HEADER:
                raise ValueError(f"unexpected interval header in {path}: {header}")
            raw = [(row[0], row[1], row[2], row[3]) for row in reader]
    return [(a, b, float(c), float(d)) for a, b, c, d in raw]


def write_default_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_HEADER)
        writer.writerows(default_rows())
