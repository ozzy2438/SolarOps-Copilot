"""Electricity bill PDFs. Owned by: Phase 2.

Two retailer layouts so extraction cannot overfit. Every bill labels the NMI
explicitly so redaction preserves the join key.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from voltdesk.synthetic.identities import Identity
from voltdesk.synthetic.spec import Defect, RetailerLayout

_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def dmy(value: date) -> str:
    return f"{value.day:02d}/{value.month:02d}/{value.year}"


def d_mon(value: date) -> str:
    return f"{value.day} {_MONTHS[value.month - 1]} {value.year}"


@dataclass
class BillFacts:
    identity: Identity
    layout: RetailerLayout
    tariff: dict[str, Any]
    period_start: date
    period_end: date
    issue_date: date
    consumption_kwh: float
    peak_kwh: float
    offpeak_kwh: float
    solar_export_kwh: float | None
    daily_supply_aud: float
    usage_aud: float
    total_aud: float
    defects: list[Defect]
    period_start_text: str
    period_end_text: str
    issue_text: str

    @property
    def tariff_type(self) -> str:
        return str(self.tariff["tariff_type"])

    @property
    def days(self) -> int:
        return (self.period_end - self.period_start).days + 1


def build_facts(
    identity: Identity,
    layout: RetailerLayout,
    tariff: dict[str, Any],
    period_start: date,
    consumption_kwh: float,
    peak_kwh: float,
    offpeak_kwh: float,
    solar_export_kwh: float | None,
    defects: list[Defect],
) -> BillFacts:
    days = 90
    period_end = period_start + timedelta(days=days - 1)
    issue = period_end + timedelta(days=8)
    daily = float(tariff["daily_supply_aud"]) * days
    if tariff["tariff_type"] == "time_of_use":
        usage = peak_kwh * float(tariff["peak_aud_per_kwh"]) + offpeak_kwh * float(
            tariff["offpeak_aud_per_kwh"]
        )
    else:
        usage = consumption_kwh * float(tariff["usage_aud_per_kwh"])
    total = round(daily + usage, 2)
    mixed = Defect.INCONSISTENT_DATE_FORMAT in defects
    return BillFacts(
        identity=identity,
        layout=layout,
        tariff=tariff,
        period_start=period_start,
        period_end=period_end,
        issue_date=issue,
        consumption_kwh=round(consumption_kwh, 1),
        peak_kwh=round(peak_kwh, 1),
        offpeak_kwh=round(offpeak_kwh, 1),
        solar_export_kwh=(
            None
            if Defect.MISSING_FIELD in defects
            else (None if solar_export_kwh is None else round(solar_export_kwh, 1))
        ),
        daily_supply_aud=round(daily, 2),
        usage_aud=round(usage, 2),
        total_aud=total,
        defects=defects,
        period_start_text=dmy(period_start),
        period_end_text=d_mon(period_end) if mixed else dmy(period_end),
        issue_text=d_mon(issue) if layout == RetailerLayout.RETAILER_B or mixed else dmy(issue),
    )


def ground_truth(facts: BillFacts) -> dict[str, object]:
    return {
        "retailer_name": facts.identity.retailer_name,
        "nmi": facts.identity.nmi,
        "account_number": facts.identity.account_number,
        "site_address": facts.identity.site_address,
        "billing_period.start": facts.period_start.isoformat(),
        "billing_period.end": facts.period_end.isoformat(),
        "issue_date": facts.issue_date.isoformat(),
        "total_amount.amount": facts.total_aud,
        "total_amount.is_gst_inclusive": True,
        "total_consumption_kwh": facts.consumption_kwh,
        "peak_demand_kva": None,
        "tariff_type": facts.tariff_type,
        "tariff_code": facts.tariff["tariff_code"],
        "solar_export_kwh": facts.solar_export_kwh,
        "phase_configuration": "three_phase",
        "page_count": 2 if Defect.MULTI_PAGE_TABLE_SPLIT in facts.defects else 1,
    }


def write_bill_pdf(path: Path, facts: BillFacts) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    split = Defect.MULTI_PAGE_TABLE_SPLIT in facts.defects
    skew = Defect.SKEWED_SCAN in facts.defects
    if Defect.LOW_CONTRAST_PHOTOCOPY in facts.defects:
        gray = colors.Color(0.45, 0.45, 0.45)
    else:
        gray = colors.black
    c = canvas.Canvas(buffer, pagesize=A4, invariant=1)
    _draw_page(c, facts, gray=gray, page=1, split=split)
    if skew:
        c.setPageRotation(90)
    c.showPage()
    if split:
        _draw_page(c, facts, gray=gray, page=2, split=True)
        c.showPage()
    c.save()
    data = buffer.getvalue()
    if Defect.NO_TEXT_LAYER in facts.defects:
        data = _as_image_pdf(facts)
    path.write_bytes(data)


def _draw_page(
    c: canvas.Canvas, facts: BillFacts, *, gray: colors.Color, page: int, split: bool
) -> None:
    c.setFillColor(gray)
    y = 800
    ident = facts.identity
    if page == 1:
        if facts.layout == RetailerLayout.RETAILER_A:
            title = ident.retailer_name.upper()
        else:
            title = "ELECTRICITY ACCOUNT"
        c.setFont("Times-Bold", 16)
        c.drawString(40, y, title)
        y -= 24
        c.setFont("Times-Roman", 10)
        lines = [
            f"Customer: {ident.company_name}",
            f"Account {ident.account_number}",
            f"NMI {ident.nmi}",
            f"National Metering Identifier: {ident.nmi}",
            f"Site: {ident.site_address}",
            f"Billing period: {facts.period_start_text} to {facts.period_end_text}",
            f"Issue date: {facts.issue_text}",
            f"Tariff {facts.tariff['tariff_code']} ({facts.tariff_type})",
            f"Contact {ident.email} / {ident.phone}",
        ]
        for line in lines:
            c.drawString(40, y, line)
            y -= 14
        y -= 8
        c.setFont("Times-Bold", 10)
        c.drawString(40, y, "Component")
        c.drawString(220, y, "Rate")
        c.drawString(340, y, "Quantity")
        c.drawString(460, y, "Amount AUD")
        y -= 16
        c.setFont("Times-Roman", 10)
        rows = _component_rows(facts)
        if split:
            rows = rows[:2]
        for row in rows:
            c.drawString(40, y, row[0])
            c.drawString(220, y, row[1])
            c.drawString(340, y, row[2])
            c.drawString(460, y, row[3])
            y -= 14
        if not split:
            _totals(c, facts, y)
    else:
        c.setFont("Times-Roman", 10)
        c.drawString(40, y, f"Continued — NMI {ident.nmi}")
        y -= 20
        for row in _component_rows(facts)[2:]:
            c.drawString(40, y, row[0])
            c.drawString(220, y, row[1])
            c.drawString(340, y, row[2])
            c.drawString(460, y, row[3])
            y -= 14
        _totals(c, facts, y)


def _component_rows(facts: BillFacts) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = [
        (
            "Daily supply",
            f"{facts.tariff['daily_supply_aud']:.4f} AUD/day",
            f"{facts.days} days",
            f"{facts.daily_supply_aud:.2f}",
        )
    ]
    if facts.tariff_type == "time_of_use":
        rows.append(
            (
                "Peak usage 9am-9pm weekdays",
                f"{float(facts.tariff['peak_aud_per_kwh']) * 100:.2f} c/kWh",
                f"{facts.peak_kwh:.1f} kWh",
                f"{facts.peak_kwh * float(facts.tariff['peak_aud_per_kwh']):.2f}",
            )
        )
        rows.append(
            (
                "Off-peak usage",
                f"{float(facts.tariff['offpeak_aud_per_kwh']) * 100:.2f} c/kWh",
                f"{facts.offpeak_kwh:.1f} kWh",
                f"{facts.offpeak_kwh * float(facts.tariff['offpeak_aud_per_kwh']):.2f}",
            )
        )
    else:
        rows.append(
            (
                "General usage",
                f"{float(facts.tariff['usage_aud_per_kwh']) * 100:.2f} c/kWh",
                f"{facts.consumption_kwh:.1f} kWh",
                f"{facts.usage_aud:.2f}",
            )
        )
    if facts.solar_export_kwh is not None:
        rows.append(("Solar export", "credit", f"{facts.solar_export_kwh:.1f} kWh", "0.00"))
    return rows


def _totals(c: canvas.Canvas, facts: BillFacts, y: float) -> None:
    c.setFont("Times-Bold", 11)
    c.drawString(40, y - 10, f"Total (GST inclusive): {facts.total_aud:.2f} AUD")
    c.setFont("Times-Roman", 10)
    c.drawString(40, y - 26, f"Total consumption: {facts.consumption_kwh:.1f} kWh")
    c.drawString(40, y - 40, "Phase configuration: three_phase")


def _as_image_pdf(facts: BillFacts) -> bytes:
    """Image-only PDF so the parser must take the OCR path."""
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader

    image = Image.new("RGB", (595, 842), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    lines = [
        facts.identity.retailer_name,
        f"NMI {facts.identity.nmi}",
        f"Account {facts.identity.account_number}",
        facts.identity.site_address,
        f"Period {facts.period_start_text} to {facts.period_end_text}",
        f"Total {facts.total_aud:.2f} AUD",
        f"Consumption {facts.consumption_kwh:.1f} kWh",
    ]
    y = 40
    for line in lines:
        draw.text((40, y), line, fill=(20, 20, 20), font=font)
        y += 18
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4, invariant=1)
    c.drawImage(ImageReader(buf), 0, 0, width=595, height=842)
    c.showPage()
    c.save()
    return out.getvalue()
