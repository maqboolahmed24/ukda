from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

AllowedContentType = str

_EXTENSION_TO_CONTENT_TYPE: dict[str, AllowedContentType] = {
    ".pdf": "application/pdf",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


@dataclass(frozen=True)
class FileTypeValidationResult:
    extension: str
    expected_content_type: AllowedContentType
    detected_content_type: AllowedContentType


class DocumentUploadValidationError(RuntimeError):
    """Upload payload does not satisfy controlled ingest validation rules."""


def parse_allowed_extension(filename: str) -> tuple[str, AllowedContentType]:
    extension = Path(filename).suffix.lower()
    expected = _EXTENSION_TO_CONTENT_TYPE.get(extension)
    if expected is None:
        raise DocumentUploadValidationError(
            "Unsupported file extension. Allowed: PDF, TIFF, PNG, JPG, JPEG."
        )
    return extension, expected


def detect_content_type_from_magic(prefix_bytes: bytes) -> AllowedContentType:
    if prefix_bytes.startswith(b"%PDF-"):
        return "application/pdf"
    if prefix_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if prefix_bytes.startswith((b"\xff\xd8\xff",)):
        return "image/jpeg"
    if prefix_bytes.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    raise DocumentUploadValidationError("Uploaded file signature is unsupported.")


def validate_extension_matches_magic(
    *,
    filename: str,
    prefix_bytes: bytes,
) -> FileTypeValidationResult:
    extension, expected_content_type = parse_allowed_extension(filename)
    detected_content_type = detect_content_type_from_magic(prefix_bytes)
    if detected_content_type != expected_content_type:
        raise DocumentUploadValidationError(
            "Uploaded file signature does not match the selected file extension."
        )
    return FileTypeValidationResult(
        extension=extension,
        expected_content_type=expected_content_type,
        detected_content_type=detected_content_type,
    )

