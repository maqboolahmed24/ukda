from __future__ import annotations

import struct

from app.documents.extraction import resolve_source_metadata


def _build_two_page_tiff_payload() -> bytes:
    # Header: little-endian TIFF with first IFD at offset 8.
    payload = bytearray()
    payload.extend(b"II")
    payload.extend(struct.pack("<H", 42))
    payload.extend(struct.pack("<I", 8))

    # First IFD: width + height tags.
    payload.extend(struct.pack("<H", 2))
    payload.extend(struct.pack("<H", 256))  # ImageWidth
    payload.extend(struct.pack("<H", 4))  # LONG
    payload.extend(struct.pack("<I", 1))
    payload.extend(struct.pack("<I", 1000))
    payload.extend(struct.pack("<H", 257))  # ImageLength
    payload.extend(struct.pack("<H", 4))  # LONG
    payload.extend(struct.pack("<I", 1))
    payload.extend(struct.pack("<I", 1400))
    payload.extend(struct.pack("<I", 38))  # next IFD offset

    # Second IFD: empty entry list and no next IFD.
    payload.extend(struct.pack("<H", 0))
    payload.extend(struct.pack("<I", 0))
    return bytes(payload)


def test_pdf_source_metadata_counts_pages() -> None:
    payload = b"%PDF-1.7\n1 0 obj << /Type /Page >>\n2 0 obj << /Type /Page >>"
    metadata = resolve_source_metadata(content_type="application/pdf", payload=payload)

    assert metadata.page_count == 2
    assert metadata.width == 1000
    assert metadata.height == 1400
    assert metadata.dpi == 300


def test_png_source_metadata_uses_encoded_dimensions() -> None:
    payload = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x03\xe8"  # 1000
        b"\x00\x00\x05x"  # 1400
        b"\x08\x02\x00\x00\x00"
    )
    metadata = resolve_source_metadata(content_type="image/png", payload=payload)

    assert metadata.page_count == 1
    assert metadata.width == 1000
    assert metadata.height == 1400


def test_tiff_source_metadata_counts_multipage_payload() -> None:
    metadata = resolve_source_metadata(
        content_type="image/tiff",
        payload=_build_two_page_tiff_payload(),
    )

    assert metadata.page_count == 2
    assert metadata.width == 1000
    assert metadata.height == 1400
