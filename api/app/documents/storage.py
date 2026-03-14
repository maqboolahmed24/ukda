from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from shutil import rmtree
from shutil import move

from app.core.config import Settings, get_settings
from app.core.storage_boundaries import resolve_storage_boundary


class DocumentStorageError(RuntimeError):
    """Controlled document storage could not complete the operation."""


@dataclass(frozen=True)
class StoredDocumentObject:
    object_key: str
    absolute_path: Path


class DocumentStorage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._boundary = resolve_storage_boundary(settings)

    @staticmethod
    def _normalize_prefix(value: str) -> str:
        return value.strip("/ ")

    def _resolve_file_path(self, object_key: str) -> Path:
        key = object_key.lstrip("/")
        return self._settings.storage_controlled_root / key

    def _build_object_key(self, *, project_id: str, document_id: str) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_raw_prefix)
        object_key = f"{prefix}/{project_id}/{document_id}/original.bin"
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled raw object key violates storage boundaries.")
        return object_key

    def _build_source_meta_object_key(self, *, project_id: str, document_id: str) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_raw_prefix)
        object_key = f"{prefix}/{project_id}/{document_id}/source-meta.json"
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled raw object key violates storage boundaries.")
        return object_key

    def _build_upload_session_chunk_key(
        self,
        *,
        project_id: str,
        session_id: str,
        chunk_index: int,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_raw_prefix)
        object_key = (
            f"{prefix}/_upload-sessions/{project_id}/{session_id}/chunks/{chunk_index}.part"
        )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Upload session key violates storage boundaries.")
        return object_key

    def _build_derived_page_key(
        self,
        *,
        project_id: str,
        document_id: str,
        page_index: int,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        object_key = f"{prefix}/{project_id}/{document_id}/pages/{page_index}.png"
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_derived_thumbnail_key(
        self,
        *,
        project_id: str,
        document_id: str,
        page_index: int,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        object_key = f"{prefix}/{project_id}/{document_id}/thumbs/{page_index}.jpg"
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_preprocess_gray_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        object_key = f"{prefix}/{project_id}/{document_id}/preprocess/{run_id}/gray/{page_index}.png"
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_preprocess_bin_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        object_key = f"{prefix}/{project_id}/{document_id}/preprocess/{run_id}/bin/{page_index}.png"
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_preprocess_metrics_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        object_key = (
            f"{prefix}/{project_id}/{document_id}/preprocess/{run_id}/metrics/{page_index}.json"
        )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_preprocess_manifest_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        object_key = f"{prefix}/{project_id}/{document_id}/preprocess/{run_id}/manifest.json"
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_layout_page_xml_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        layout_version_id: str | None = None,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        if isinstance(layout_version_id, str) and layout_version_id.strip():
            object_key = (
                f"{prefix}/{project_id}/{document_id}/layout/{run_id}/versions/"
                f"{layout_version_id.strip()}/page/{page_index}.xml"
            )
        else:
            object_key = (
                f"{prefix}/{project_id}/{document_id}/layout/{run_id}/page/{page_index}.xml"
            )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_layout_page_overlay_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        layout_version_id: str | None = None,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        if isinstance(layout_version_id, str) and layout_version_id.strip():
            object_key = (
                f"{prefix}/{project_id}/{document_id}/layout/{run_id}/versions/"
                f"{layout_version_id.strip()}/page/{page_index}.json"
            )
        else:
            object_key = (
                f"{prefix}/{project_id}/{document_id}/layout/{run_id}/page/{page_index}.json"
            )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_layout_manifest_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        object_key = f"{prefix}/{project_id}/{document_id}/layout/{run_id}/manifest.json"
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_layout_page_thumbnail_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        layout_version_id: str | None = None,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        if isinstance(layout_version_id, str) and layout_version_id.strip():
            object_key = (
                f"{prefix}/{project_id}/{document_id}/layout/{run_id}/versions/"
                f"{layout_version_id.strip()}/page/{page_index}/thumbnail.png"
            )
        else:
            object_key = (
                f"{prefix}/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/thumbnail.png"
            )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_layout_line_crop_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
        layout_version_id: str | None = None,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        if isinstance(layout_version_id, str) and layout_version_id.strip():
            object_key = (
                f"{prefix}/{project_id}/{document_id}/layout/{run_id}/versions/"
                f"{layout_version_id.strip()}/page/{page_index}/lines/{line_id}.png"
            )
        else:
            object_key = (
                f"{prefix}/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/lines/{line_id}.png"
            )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_layout_region_crop_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        region_id: str,
        layout_version_id: str | None = None,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        if isinstance(layout_version_id, str) and layout_version_id.strip():
            object_key = (
                f"{prefix}/{project_id}/{document_id}/layout/{run_id}/versions/"
                f"{layout_version_id.strip()}/page/{page_index}/regions/{region_id}.png"
            )
        else:
            object_key = (
                f"{prefix}/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/regions/{region_id}.png"
            )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_layout_context_window_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
        layout_version_id: str | None = None,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        if isinstance(layout_version_id, str) and layout_version_id.strip():
            object_key = (
                f"{prefix}/{project_id}/{document_id}/layout/{run_id}/versions/"
                f"{layout_version_id.strip()}/page/{page_index}/context/{line_id}.json"
            )
        else:
            object_key = (
                f"{prefix}/{project_id}/{document_id}/layout/{run_id}/page/{page_index}/context/{line_id}.json"
            )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_transcription_page_xml_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        transcript_version_id: str | None = None,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        if isinstance(transcript_version_id, str) and transcript_version_id.strip():
            object_key = (
                f"{prefix}/{project_id}/{document_id}/transcription/{run_id}/versions/"
                f"{transcript_version_id.strip()}/page/{page_index}.xml"
            )
        else:
            object_key = (
                f"{prefix}/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}.xml"
            )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_transcription_raw_response_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        object_key = (
            f"{prefix}/{project_id}/{document_id}/transcription/{run_id}/page/"
            f"{page_index}.response.json"
        )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_transcription_hocr_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        object_key = (
            f"{prefix}/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}.hocr"
        )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_transcription_line_alignment_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        object_key = (
            f"{prefix}/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}/"
            f"lines/{line_id}.alignment.json"
        )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    def _build_transcription_line_char_boxes_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
    ) -> str:
        prefix = self._normalize_prefix(self._settings.storage_controlled_derived_prefix)
        object_key = (
            f"{prefix}/{project_id}/{document_id}/transcription/{run_id}/page/{page_index}/"
            f"lines/{line_id}.char-boxes.json"
        )
        if not self._boundary.can_write(writer="app", object_key=object_key):
            raise DocumentStorageError("Controlled derived object key violates storage boundaries.")
        return object_key

    @staticmethod
    def _write_idempotent(destination: Path, payload: bytes) -> None:
        if destination.exists():
            try:
                current = destination.read_bytes()
            except OSError as error:
                raise DocumentStorageError("Controlled derived object could not be read.") from error
            if current != payload:
                raise DocumentStorageError(
                    "Controlled derived object already exists with different content."
                )
            return
        try:
            with destination.open("xb") as handle:
                handle.write(payload)
            destination.chmod(0o600)
        except OSError as error:
            raise DocumentStorageError("Controlled derived object could not be persisted.") from error

    @staticmethod
    def _require_new_destination(destination: Path) -> None:
        if destination.exists():
            raise DocumentStorageError("Controlled raw object already exists and is immutable.")

    def write_original(
        self,
        *,
        project_id: str,
        document_id: str,
        source_path: Path,
    ) -> StoredDocumentObject:
        object_key = self._build_object_key(project_id=project_id, document_id=document_id)
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._require_new_destination(destination)
            move(str(source_path), str(destination))
            destination.chmod(0o600)
        except OSError as error:
            raise DocumentStorageError("Controlled raw object could not be persisted.") from error

        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def resolve_upload_session_chunk_path(
        self,
        *,
        project_id: str,
        session_id: str,
        chunk_index: int,
    ) -> Path:
        object_key = self._build_upload_session_chunk_key(
            project_id=project_id,
            session_id=session_id,
            chunk_index=chunk_index,
        )
        return self._resolve_file_path(object_key)

    def append_upload_session_chunk(
        self,
        *,
        project_id: str,
        session_id: str,
        chunk_index: int,
        payload: bytes,
    ) -> Path:
        if not payload:
            raise DocumentStorageError("Upload session chunk is empty.")
        destination = self.resolve_upload_session_chunk_path(
            project_id=project_id,
            session_id=session_id,
            chunk_index=chunk_index,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            if destination.exists():
                existing = destination.read_bytes()
                if existing != payload:
                    raise DocumentStorageError(
                        "Upload session chunk collision detected for this index."
                    )
                return destination
            with destination.open("xb") as handle:
                handle.write(payload)
            destination.chmod(0o600)
        except OSError as error:
            raise DocumentStorageError("Upload session chunk could not be persisted.") from error
        return destination

    def clear_upload_session_chunks(self, *, project_id: str, session_id: str) -> None:
        marker = self.resolve_upload_session_chunk_path(
            project_id=project_id,
            session_id=session_id,
            chunk_index=0,
        )
        path = marker.parent.parent
        if not path.exists():
            return
        try:
            rmtree(path)
        except OSError as error:
            raise DocumentStorageError("Upload session chunk cleanup failed.") from error

    def move_upload_session_into_original(
        self,
        *,
        project_id: str,
        document_id: str,
        session_id: str,
        last_chunk_index: int,
    ) -> StoredDocumentObject:
        temp_handle = tempfile.NamedTemporaryFile(
            prefix="ukde-upload-assemble-",
            suffix=".bin",
            delete=False,
        )
        temp_path = Path(temp_handle.name)
        try:
            with temp_path.open("wb") as assembled:
                for chunk_index in range(last_chunk_index + 1):
                    chunk_path = self.resolve_upload_session_chunk_path(
                        project_id=project_id,
                        session_id=session_id,
                        chunk_index=chunk_index,
                    )
                    if not chunk_path.exists():
                        raise DocumentStorageError(
                            f"Upload session chunk {chunk_index} is missing."
                        )
                    assembled.write(chunk_path.read_bytes())
            stored = self.write_original(
                project_id=project_id,
                document_id=document_id,
                source_path=temp_path,
            )
        except OSError as error:
            raise DocumentStorageError("Upload session payload assembly failed.") from error
        finally:
            try:
                temp_handle.close()
            except OSError:
                pass
            temp_path.unlink(missing_ok=True)
        return stored

    def write_source_metadata(
        self,
        *,
        project_id: str,
        document_id: str,
        metadata: dict[str, object],
    ) -> StoredDocumentObject:
        object_key = self._build_source_meta_object_key(
            project_id=project_id,
            document_id=document_id,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        serialized = (
            json.dumps(
                metadata,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )

        try:
            self._require_new_destination(destination)
            with destination.open("xb") as handle:
                handle.write(serialized)
            destination.chmod(0o600)
        except OSError as error:
            raise DocumentStorageError("Controlled source metadata could not be persisted.") from error

        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def resolve_object_path(self, object_key: str) -> Path:
        return self._resolve_file_path(object_key)

    def write_derived_page_image(
        self,
        *,
        project_id: str,
        document_id: str,
        page_index: int,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_derived_page_key(
            project_id=project_id,
            document_id=document_id,
            page_index=page_index,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._require_new_destination(destination)
            with destination.open("xb") as handle:
                handle.write(payload)
            destination.chmod(0o600)
        except OSError as error:
            raise DocumentStorageError("Controlled derived page image could not be persisted.") from error
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_derived_thumbnail(
        self,
        *,
        project_id: str,
        document_id: str,
        page_index: int,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_derived_thumbnail_key(
            project_id=project_id,
            document_id=document_id,
            page_index=page_index,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._require_new_destination(destination)
            with destination.open("xb") as handle:
                handle.write(payload)
            destination.chmod(0o600)
        except OSError as error:
            raise DocumentStorageError("Controlled derived thumbnail could not be persisted.") from error
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_preprocess_gray_image(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_preprocess_gray_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_preprocess_bin_image(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_preprocess_bin_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_preprocess_page_metrics(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        metrics_json: dict[str, object],
    ) -> StoredDocumentObject:
        object_key = self._build_preprocess_metrics_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps(
                metrics_json,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_preprocess_manifest(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_preprocess_manifest_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def build_layout_page_xml_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        layout_version_id: str | None = None,
    ) -> str:
        return self._build_layout_page_xml_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            layout_version_id=layout_version_id,
        )

    def build_layout_page_overlay_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        layout_version_id: str | None = None,
    ) -> str:
        return self._build_layout_page_overlay_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            layout_version_id=layout_version_id,
        )

    def build_layout_manifest_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
    ) -> str:
        return self._build_layout_manifest_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )

    def build_layout_page_thumbnail_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        layout_version_id: str | None = None,
    ) -> str:
        return self._build_layout_page_thumbnail_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            layout_version_id=layout_version_id,
        )

    def build_layout_line_crop_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
        layout_version_id: str | None = None,
    ) -> str:
        return self._build_layout_line_crop_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            line_id=line_id,
            layout_version_id=layout_version_id,
        )

    def build_layout_region_crop_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        region_id: str,
        layout_version_id: str | None = None,
    ) -> str:
        return self._build_layout_region_crop_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            region_id=region_id,
            layout_version_id=layout_version_id,
        )

    def build_layout_context_window_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
        layout_version_id: str | None = None,
    ) -> str:
        return self._build_layout_context_window_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            line_id=line_id,
            layout_version_id=layout_version_id,
        )

    def write_layout_page_xml(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        layout_version_id: str | None = None,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_layout_page_xml_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            layout_version_id=layout_version_id,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_layout_page_overlay(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        layout_version_id: str | None = None,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_layout_page_overlay_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            layout_version_id=layout_version_id,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_layout_page_thumbnail(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        layout_version_id: str | None = None,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_layout_page_thumbnail_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            layout_version_id=layout_version_id,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_layout_line_crop(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
        layout_version_id: str | None = None,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_layout_line_crop_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            line_id=line_id,
            layout_version_id=layout_version_id,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_layout_region_crop(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        region_id: str,
        layout_version_id: str | None = None,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_layout_region_crop_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            region_id=region_id,
            layout_version_id=layout_version_id,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_layout_context_window(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
        layout_version_id: str | None = None,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_layout_context_window_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            line_id=line_id,
            layout_version_id=layout_version_id,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_layout_manifest(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_layout_manifest_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def build_transcription_page_xml_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
    ) -> str:
        return self._build_transcription_page_xml_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
        )

    def build_transcription_corrected_page_xml_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        transcript_version_id: str,
    ) -> str:
        return self._build_transcription_page_xml_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            transcript_version_id=transcript_version_id,
        )

    def build_transcription_raw_response_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
    ) -> str:
        return self._build_transcription_raw_response_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
        )

    def build_transcription_hocr_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
    ) -> str:
        return self._build_transcription_hocr_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
        )

    def build_transcription_line_alignment_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
    ) -> str:
        return self._build_transcription_line_alignment_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            line_id=line_id,
        )

    def build_transcription_line_char_boxes_key(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
    ) -> str:
        return self._build_transcription_line_char_boxes_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            line_id=line_id,
        )

    def write_transcription_page_xml(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_transcription_page_xml_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_transcription_corrected_page_xml(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        transcript_version_id: str,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_transcription_page_xml_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            transcript_version_id=transcript_version_id,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_transcription_raw_response(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_transcription_raw_response_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_transcription_hocr(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_transcription_hocr_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_transcription_line_alignment(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_transcription_line_alignment_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            line_id=line_id,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def write_transcription_line_char_boxes(
        self,
        *,
        project_id: str,
        document_id: str,
        run_id: str,
        page_index: int,
        line_id: str,
        payload: bytes,
    ) -> StoredDocumentObject:
        object_key = self._build_transcription_line_char_boxes_key(
            project_id=project_id,
            document_id=document_id,
            run_id=run_id,
            page_index=page_index,
            line_id=line_id,
        )
        destination = self._resolve_file_path(object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_idempotent(destination, payload)
        return StoredDocumentObject(object_key=object_key, absolute_path=destination)

    def read_object_bytes(self, object_key: str) -> bytes:
        path = self._resolve_file_path(object_key)
        try:
            return path.read_bytes()
        except OSError as error:
            raise DocumentStorageError("Controlled document object could not be read.") from error


@lru_cache
def get_document_storage() -> DocumentStorage:
    settings = get_settings()
    return DocumentStorage(settings=settings)
