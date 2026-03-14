from __future__ import annotations

import re
import struct
from dataclasses import dataclass

_DEFAULT_WIDTH = 1000
_DEFAULT_HEIGHT = 1400

# 1x1 transparent PNG
_PLACEHOLDER_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
    b"\x0b\xe7\x02\x9b"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

# 1x1 JPEG
_PLACEHOLDER_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300"
    "0302020302020303030304040304050805050404050a070706"
    "080c0a0c0c0b0a0b0b0d0e12100d0e110e0b0b101610111314"
    "1515150c0f171816141812141514ffdb004301030303040304"
    "08040408140d0b0d1414141414141414141414141414141414"
    "14141414141414141414141414141414141414141414141414"
    "1414141414ffc00011080001000103012200021101031101ff"
    "c40014000100000000000000000000000000000000ffc40014"
    "100100000000000000000000000000000000ffc40014010100"
    "000000000000000000000000000000ffc40014110100000000"
    "00000000000000000000000000ffda000c0301000211031100"
    "3f00ffd9"
)


@dataclass(frozen=True)
class ExtractedSourceMetadata:
    page_count: int
    width: int
    height: int
    dpi: int | None


def placeholder_png_bytes() -> bytes:
    return _PLACEHOLDER_PNG


def placeholder_jpeg_bytes() -> bytes:
    return _PLACEHOLDER_JPEG


def resolve_source_metadata(*, content_type: str, payload: bytes) -> ExtractedSourceMetadata:
    normalized = content_type.strip().lower()
    if normalized == "application/pdf":
        page_count = _count_pdf_pages(payload)
        return ExtractedSourceMetadata(
            page_count=max(1, page_count),
            width=_DEFAULT_WIDTH,
            height=_DEFAULT_HEIGHT,
            dpi=300,
        )
    if normalized == "image/tiff":
        page_count, width, height = _parse_tiff(payload)
        return ExtractedSourceMetadata(
            page_count=max(1, page_count),
            width=width or _DEFAULT_WIDTH,
            height=height or _DEFAULT_HEIGHT,
            dpi=300,
        )
    if normalized == "image/png":
        width, height = _parse_png_dimensions(payload)
        return ExtractedSourceMetadata(
            page_count=1,
            width=width or _DEFAULT_WIDTH,
            height=height or _DEFAULT_HEIGHT,
            dpi=300,
        )
    if normalized == "image/jpeg":
        width, height = _parse_jpeg_dimensions(payload)
        return ExtractedSourceMetadata(
            page_count=1,
            width=width or _DEFAULT_WIDTH,
            height=height or _DEFAULT_HEIGHT,
            dpi=300,
        )

    return ExtractedSourceMetadata(
        page_count=1,
        width=_DEFAULT_WIDTH,
        height=_DEFAULT_HEIGHT,
        dpi=300,
    )


def _count_pdf_pages(payload: bytes) -> int:
    matches = re.findall(rb"/Type\s*/Page\b", payload)
    if not matches:
        return 1
    return len(matches)


def _parse_png_dimensions(payload: bytes) -> tuple[int | None, int | None]:
    if len(payload) < 24:
        return None, None
    if payload[:8] != b"\x89PNG\r\n\x1a\n":
        return None, None
    if payload[12:16] != b"IHDR":
        return None, None
    width = int.from_bytes(payload[16:20], "big", signed=False)
    height = int.from_bytes(payload[20:24], "big", signed=False)
    if width < 1 or height < 1:
        return None, None
    return width, height


def _parse_jpeg_dimensions(payload: bytes) -> tuple[int | None, int | None]:
    if len(payload) < 4 or payload[0:2] != b"\xff\xd8":
        return None, None
    idx = 2
    length = len(payload)
    while idx + 1 < length:
        if payload[idx] != 0xFF:
            idx += 1
            continue
        marker = payload[idx + 1]
        idx += 2
        if marker in {0xD8, 0xD9}:
            continue
        if idx + 1 >= length:
            break
        segment_len = int.from_bytes(payload[idx: idx + 2], "big")
        if segment_len < 2 or idx + segment_len > length:
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if segment_len >= 7:
                height = int.from_bytes(payload[idx + 3: idx + 5], "big")
                width = int.from_bytes(payload[idx + 5: idx + 7], "big")
                if width > 0 and height > 0:
                    return width, height
            break
        idx += segment_len
    return None, None


def _parse_tiff(payload: bytes) -> tuple[int, int | None, int | None]:
    if len(payload) < 8:
        return 1, None, None
    order = payload[:2]
    if order == b"II":
        endian = "<"
    elif order == b"MM":
        endian = ">"
    else:
        return 1, None, None

    magic = struct.unpack_from(f"{endian}H", payload, 2)[0]
    if magic != 42:
        return 1, None, None

    first_ifd_offset = struct.unpack_from(f"{endian}I", payload, 4)[0]
    if first_ifd_offset <= 0 or first_ifd_offset >= len(payload):
        return 1, None, None

    width: int | None = None
    height: int | None = None
    page_count = 0
    next_ifd_offset = first_ifd_offset
    loop_guard = 0

    while next_ifd_offset > 0 and next_ifd_offset < len(payload) and loop_guard < 8192:
        loop_guard += 1
        if next_ifd_offset + 2 > len(payload):
            break
        entry_count = struct.unpack_from(f"{endian}H", payload, next_ifd_offset)[0]
        entries_offset = next_ifd_offset + 2
        if entries_offset + entry_count * 12 + 4 > len(payload):
            break
        if page_count == 0:
            width, height = _parse_tiff_first_dimensions(
                payload=payload,
                endian=endian,
                entries_offset=entries_offset,
                entry_count=entry_count,
            )
        next_ifd_offset = struct.unpack_from(
            f"{endian}I",
            payload,
            entries_offset + entry_count * 12,
        )[0]
        page_count += 1

    return max(1, page_count), width, height


def _parse_tiff_first_dimensions(
    *,
    payload: bytes,
    endian: str,
    entries_offset: int,
    entry_count: int,
) -> tuple[int | None, int | None]:
    width: int | None = None
    height: int | None = None
    for idx in range(entry_count):
        entry_start = entries_offset + idx * 12
        tag = struct.unpack_from(f"{endian}H", payload, entry_start)[0]
        value_type = struct.unpack_from(f"{endian}H", payload, entry_start + 2)[0]
        value_count = struct.unpack_from(f"{endian}I", payload, entry_start + 4)[0]
        value_or_offset = payload[entry_start + 8: entry_start + 12]
        if value_count < 1:
            continue
        value = _parse_tiff_inline_value(value_type=value_type, raw=value_or_offset, endian=endian)
        if value is None:
            continue
        if tag == 256 and width is None:
            width = value
        if tag == 257 and height is None:
            height = value
        if width is not None and height is not None:
            break
    return width, height


def _parse_tiff_inline_value(*, value_type: int, raw: bytes, endian: str) -> int | None:
    if value_type == 3:  # SHORT
        return struct.unpack(f"{endian}H", raw[:2])[0]
    if value_type == 4:  # LONG
        return struct.unpack(f"{endian}I", raw)[0]
    return None
