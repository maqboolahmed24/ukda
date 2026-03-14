from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.core.config import Settings, get_settings

ScannerVerdict = Literal["CLEAN", "REJECTED"]


class DocumentScannerUnavailableError(RuntimeError):
    """No scanner backend is configured for this environment."""


@dataclass(frozen=True)
class ScannerResult:
    verdict: ScannerVerdict
    reason: str | None = None


class DocumentScanner:
    def scan_file(
        self,
        *,
        file_path: Path,
        content_type: str,
        sha256: str,
    ) -> ScannerResult:
        raise NotImplementedError


class StubDocumentScanner(DocumentScanner):
    _eicar_token = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"

    def scan_file(
        self,
        *,
        file_path: Path,
        content_type: str,
        sha256: str,
    ) -> ScannerResult:
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 64)
                if not chunk:
                    break
                if self._eicar_token in chunk:
                    return ScannerResult(
                        verdict="REJECTED",
                        reason="Deterministic scanner rejected the upload sample.",
                    )
        return ScannerResult(verdict="CLEAN")


class UnavailableDocumentScanner(DocumentScanner):
    def scan_file(
        self,
        *,
        file_path: Path,
        content_type: str,
        sha256: str,
    ) -> ScannerResult:
        raise DocumentScannerUnavailableError("No malware scanner backend is configured.")


def resolve_document_scanner(*, settings: Settings) -> DocumentScanner:
    if settings.effective_document_scanner_backend == "stub":
        return StubDocumentScanner()
    return UnavailableDocumentScanner()


@lru_cache
def get_document_scanner() -> DocumentScanner:
    settings = get_settings()
    return resolve_document_scanner(settings=settings)

