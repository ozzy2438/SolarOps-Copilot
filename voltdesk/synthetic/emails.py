"""Inbound email threads. Owned by: Phase 2.

Quoted history is injected on purpose. A naive parser that keeps every quoted
block will repeat the first message and the token cost will scale quadratically.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

from voltdesk.synthetic.identities import Identity
from voltdesk.synthetic.spec import Defect


def write_email_thread(
    path: Path,
    identity: Identity,
    *,
    index: int,
    defects: list[Defect],
) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    quoted = Defect.QUOTED_EMAIL_HISTORY in defects
    start = datetime(2026, 2, 1, 9, 15, tzinfo=UTC) + timedelta(days=index)
    subject = f"Quote request — {identity.company_name} {identity.site_address}"
    first = (
        f"Hi, we need a {50 + (index % 4) * 25} kW rooftop system at "
        f"{identity.site_address}. Battery around {index % 3 * 20} kWh if it fits. "
        f"Deadline {(start.date() + timedelta(days=21)).isoformat()}."
    )
    reply = (
        f"Thanks {identity.person_name}, we can site-visit next week. "
        f"Confirming NMI {identity.nmi}."
    )
    follow = "Please send the connection application reference once you have it."

    messages = [
        (start, identity.email, "ops@voltdesk.example", first),
        (start + timedelta(hours=5), "ops@voltdesk.example", identity.email, reply),
        (start + timedelta(days=1), identity.email, "ops@voltdesk.example", follow),
    ]
    raw_parts: list[str] = []
    for i, (when, src, dest, body) in enumerate(messages):
        block = body
        if quoted and i > 0:
            quoted_body = "\n".join(f"> {line}" for line in first.splitlines())
            block = f"{body}\n\nOn {start.isoformat()} {identity.email} wrote:\n{quoted_body}"
        raw_parts.append(
            f"From: {src}\nTo: {dest}\nDate: {when.strftime('%a, %d %b %Y %H:%M:%S +0000')}\n"
            f"Subject: {subject if i == 0 else 'Re: ' + subject}\n\n{block}\n"
        )
    path.write_text("\n".join(raw_parts), encoding="utf-8")

    # Also write a true .eml of the latest message, for parser coverage.
    latest = EmailMessage()
    latest["From"] = identity.email
    latest["To"] = "ops@voltdesk.example"
    latest["Subject"] = "Re: " + subject
    latest["Date"] = (start + timedelta(days=1)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    latest["Message-ID"] = f"<email-{index:04d}@example.test>"
    latest.set_content(raw_parts[-1])
    path.with_suffix(".eml").write_bytes(latest.as_bytes())

    battery = float(index % 3 * 20) or None
    return {
        "thread_subject": subject,
        "intent": "quote_request",
        "company_name": identity.company_name,
        "site_address": identity.site_address,
        "requested_system_kw": float(50 + (index % 4) * 25),
        "requested_battery_kwh": battery,
        "deadline": (start.date() + timedelta(days=21)).isoformat(),
        "message_count": 3,
        "first_message_at": start.isoformat(),
        "nmi": identity.nmi,
    }
