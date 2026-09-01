"""CRM writer. Owned by: Phase 2."""

from __future__ import annotations

from helpers_phase2 import DOCUMENT_TEXT, extracted_bill, parsed_bill

from voltdesk.crm.writer import CrmWriter
from voltdesk.extraction.confidence import calibrate


class FakeCrm:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, object]] = {}

    def upsert(
        self, entity_type: str, external_key: str, payload: dict[str, object]
    ) -> tuple[dict[str, object], bool]:
        created = external_key not in self.store
        self.store[external_key] = {"entity_type": entity_type, **payload}
        return {"id": external_key, **payload}, created


def test_idempotent_write_produces_one_record() -> None:
    client = FakeCrm()
    writer = CrmWriter(client=client)
    document = parsed_bill(DOCUMENT_TEXT)
    extraction = calibrate(extracted_bill(), document)
    first = writer.write(extraction, document)
    second = writer.write(extraction, document)
    assert first.written and second.written
    assert first.external_key == second.external_key
    assert len(client.store) == 1
    assert first.created is True
    assert second.created is False


def test_blocking_uncertain_nmi_writes_nothing() -> None:
    client = FakeCrm()
    writer = CrmWriter(client=client)
    document = parsed_bill(DOCUMENT_TEXT)
    extraction = extracted_bill(nmi="6305888444", nmi_confidence=0.4, nmi_quote="NMI 6305888444")
    extraction = calibrate(extraction, document)
    outcome = writer.write(extraction, document)
    assert outcome.blocking is True
    assert outcome.written is False
    assert client.store == {}
