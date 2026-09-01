"""Deterministic text PDF writer.

Owned by: Phase 2.

No timestamps, no random IDs, no third-party PDF library. Same pages in, same
bytes out, which is what `scripts/check_generator_determinism.py` measures.
"""

from __future__ import annotations


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content_stream(lines: list[str], font_size: int = 10) -> bytes:
    if not lines:
        return b""
    parts = ["BT", f"/F1 {font_size} Tf", "36 770 Td"]
    for index, line in enumerate(lines):
        if index:
            parts.append("0 -11 Td")
        parts.append(f"({_escape(line)}) Tj")
    parts.append("ET")
    return "\n".join(parts).encode("ascii")


def _stream_object(data: bytes) -> bytes:
    return f"<< /Length {len(data)} >>\nstream\n".encode("ascii") + data + b"\nendstream"


def build_pdf(pages: list[list[str]], *, rotate: int = 0) -> bytes:
    """Build a PDF-1.4 document from per-page lines of ASCII text.

    `rotate` is the PDF page `/Rotate` value (0, 90, 180, 270). An empty page
    list becomes one blank page, which is how the no-text-layer defect is
    represented: a page with an empty content stream.
    """
    if not pages:
        pages = [[]]

    font = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"
    page_objects: list[bytes] = []
    content_objects: list[bytes] = []
    # Object numbers: 1 catalog, 2 pages, 3 font, then (page, contents) pairs.
    kids: list[str] = []
    for index, lines in enumerate(pages):
        page_num = 4 + 2 * index
        content_num = page_num + 1
        kids.append(f"{page_num} 0 R")
        rotate_part = f"/Rotate {rotate} " if rotate else ""
        page_objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_num} 0 R /Resources << /Font << /F1 3 0 R >> >> "
                f"{rotate_part}>>"
            ).encode("ascii")
        )
        content_objects.append(_stream_object(_content_stream(lines)))

    pages_obj = (
        f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    ).encode("ascii")
    catalog = b"<< /Type /Catalog /Pages 2 0 R >>"

    objects: list[bytes] = [catalog, pages_obj, font]
    for page_obj, content_obj in zip(page_objects, content_objects, strict=True):
        objects.append(page_obj)
        objects.append(content_obj)
    return _serialize(objects)


def _serialize(objects: list[bytes]) -> bytes:
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    parts: list[bytes] = [header]
    offsets = [0]
    position = len(header)
    for index, body in enumerate(objects, start=1):
        encoded = f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
        offsets.append(position)
        parts.append(encoded)
        position += len(encoded)
    xref_entries = [b"xref\n", f"0 {len(objects) + 1}\n".encode("ascii"), b"0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref_entries.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    xref = b"".join(xref_entries)
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{position}\n%%EOF\n"
    ).encode("ascii")
    return b"".join(parts) + xref + trailer
