"""Synthetic document generator.

Owned by: Phase 2. Specification is in voltdesk/synthetic/spec.py (Phase 1).
Same GeneratorConfig (including seed) produces byte-identical files.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from voltdesk.synthetic.bills import BillFacts, build_facts, ground_truth, write_bill_pdf
from voltdesk.synthetic.defects import defects_for
from voltdesk.synthetic.emails import write_email_thread
from voltdesk.synthetic.identities import fabricate
from voltdesk.synthetic.intervals import load_intervals
from voltdesk.synthetic.site_notes import default_assessed_on, write_site_notes
from voltdesk.synthetic.spec import GeneratedDocument, GeneratorConfig, RetailerLayout
from voltdesk.synthetic.tariffs import load_tariffs

_REPO_ROOT = Path(__file__).resolve().parents[2]


class SyntheticGenerator:
    """Deterministic generator. Same config -> same bytes."""

    def __init__(self, config: GeneratorConfig) -> None:
        self.config = config

    def generate(self) -> list[GeneratedDocument]:
        rng = random.Random(self.config.seed)
        out = Path(self.config.output_dir)
        if not out.is_absolute():
            out = _REPO_ROOT / out
        tariffs = load_tariffs(self.config)
        intervals = load_intervals(self.config)
        consumption, peak, offpeak, export = _quarter_totals(intervals)
        documents: list[GeneratedDocument] = []
        documents.extend(self._bills(rng, out, tariffs, consumption, peak, offpeak, export))
        documents.extend(self._sites(rng, out))
        documents.extend(self._emails(rng, out))
        return documents

    def _bills(
        self,
        rng: random.Random,
        out: Path,
        tariffs: list[dict[str, object]],
        consumption: float,
        peak: float,
        offpeak: float,
        export: float,
    ) -> list[GeneratedDocument]:
        layouts = list(self.config.layouts) or list(RetailerLayout)
        results: list[GeneratedDocument] = []
        for index in range(self.config.bill_count):
            identity = fabricate(rng, index=index)
            tariff = tariffs[index % len(tariffs)]
            layout = layouts[index % len(layouts)]
            defects = defects_for(rng, self.config, index, self.config.bill_count)
            scale = 0.7 + (index % 10) * 0.05
            facts: BillFacts = build_facts(
                identity,
                layout,
                tariff,
                date(2026, 1, 1) + timedelta(days=(index % 3) * 90),
                consumption * scale,
                peak * scale,
                offpeak * scale,
                export * scale if index % 2 else None,
                defects,
            )
            rel = f"bills/bill-{index + 1:04d}.pdf"
            path = out / rel
            write_bill_pdf(path, facts)
            meta = path.with_suffix(".json")
            truth = ground_truth(facts)
            meta.write_text(json.dumps(truth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            results.append(
                GeneratedDocument(
                    path=str(path),
                    document_type="electricity_bill",
                    defects=defects,
                    ground_truth=truth,
                )
            )
        return results

    def _sites(self, rng: random.Random, out: Path) -> list[GeneratedDocument]:
        results: list[GeneratedDocument] = []
        for index in range(self.config.site_assessment_count):
            identity = fabricate(rng, index=1000 + index)
            defects = defects_for(rng, self.config, index, self.config.site_assessment_count)
            rel = f"site_notes/site-{index + 1:04d}.txt"
            path = out / rel
            truth = write_site_notes(
                path,
                identity,
                index=index,
                assessed_on=default_assessed_on(index),
                defects=defects,
            )
            results.append(
                GeneratedDocument(
                    path=str(path),
                    document_type="site_assessment",
                    defects=defects,
                    ground_truth=truth,
                )
            )
        return results

    def _emails(self, rng: random.Random, out: Path) -> list[GeneratedDocument]:
        results: list[GeneratedDocument] = []
        for index in range(self.config.email_thread_count):
            identity = fabricate(rng, index=2000 + index)
            defects = defects_for(rng, self.config, index, self.config.email_thread_count)
            rel = f"emails/email-{index + 1:04d}.txt"
            path = out / rel
            truth = write_email_thread(path, identity, index=index, defects=defects)
            results.append(
                GeneratedDocument(
                    path=str(path),
                    document_type="email_thread",
                    defects=defects,
                    ground_truth=truth,
                )
            )
        return results


def _quarter_totals(
    intervals: list[tuple[str, str, float, float]],
) -> tuple[float, float, float, float]:
    """Scale 14 days of half-hourly shape up to a 90-day quarter."""
    consumption = peak = offpeak = export = 0.0
    for stamp, site, load, gen in intervals:
        if site != "shape-a":
            continue
        consumption += load
        export += gen
        hour = int(stamp[11:13])
        weekday = date.fromisoformat(stamp[:10]).weekday() < 5
        if weekday and 9 <= hour < 21:
            peak += load
        else:
            offpeak += load
    scale = 90 / 14
    return consumption * scale, peak * scale, offpeak * scale, export * scale
