"""Site assessment notes. Owned by: Phase 2.

Often photographed handwriting. Ground truth records absent fields as null so a
model that invents a main-switch rating is wrong, not helpful.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from voltdesk.synthetic.identities import Identity
from voltdesk.synthetic.spec import Defect

_ROOFS = ("Klip-Lok steel", "Colorbond", "concrete tile", "asbestos cement sheet")
_ORIENT = ("N", "NE", "E", "W", "NW")


def write_site_notes(
    path: Path,
    identity: Identity,
    *,
    index: int,
    assessed_on: date,
    defects: list[Defect],
) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    material = _ROOFS[index % len(_ROOFS)]
    plane_a = _ORIENT[index % len(_ORIENT)]
    plane_b = _ORIENT[(index + 2) % len(_ORIENT)]
    area_a = 200.0 + (index % 12) * 25
    area_b = 120.0 + (index % 7) * 20
    existing = 0.0 if index % 4 == 0 else 10.0 + (index % 5) * 5
    missing_switch = Defect.MISSING_FIELD in defects or index % 5 == 0
    handwritten = Defect.HANDWRITTEN_NOTES in defects
    body = [
        f"Site visit {assessed_on.isoformat()}",
        f"Address: {identity.site_address}",
        f"NMI {identity.nmi}" if index % 3 else "NMI not recorded on site",
        f"Roof: {material}",
        f"Plane {plane_a} tilt 5 deg usable {area_a:.0f} m2",
        f"Plane {plane_b} tilt 5 deg usable {area_b:.0f} m2",
        "Phase: three_phase",
        "Main switch: not recorded" if missing_switch else "Main switch 250 A",
        f"Existing PV {existing:.1f} kW" if existing else "No existing PV",
        "Battery space: yes",
        "Hazards: live parts at switchboard; height on western plane",
        "Access: internal ladder only; no crane on the western side",
        f"Assessor: {identity.person_name}",
    ]
    text = "\n".join(body)
    if handwritten:
        text = text.replace(": ", " : ").replace("Plane", "plne")
    path.write_text(text + "\n", encoding="utf-8")
    nmi_value: str | None = identity.nmi if index % 3 else None
    return {
        "site_address": identity.site_address,
        "nmi": nmi_value,
        "assessed_on": assessed_on.isoformat(),
        "roof_material": material,
        "roof_planes.0.orientation": plane_a,
        "roof_planes.0.tilt_degrees": 5.0,
        "roof_planes.0.usable_area_m2": area_a,
        "roof_planes.1.orientation": plane_b,
        "roof_planes.1.tilt_degrees": 5.0,
        "roof_planes.1.usable_area_m2": area_b,
        "phase_configuration": "three_phase",
        "main_switch_rating_a": None if missing_switch else 250.0,
        "existing_pv_kw": existing if existing else None,
        "battery_space_available": True,
        "access_constraints": "internal ladder only; no crane on the western side",
    }


def default_assessed_on(index: int) -> date:
    return date(2026, 1, 6) + timedelta(days=index * 3)
