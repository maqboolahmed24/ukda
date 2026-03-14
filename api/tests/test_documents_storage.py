from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.documents.storage import DocumentStorage, DocumentStorageError


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        APP_ENV="test",
        DATABASE_URL="postgresql://ukde:ukde@127.0.0.1:5432/ukde",
        STORAGE_CONTROLLED_ROOT=str(tmp_path),
    )


def test_controlled_storage_writes_original_and_source_meta(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)
    source_path = tmp_path / "incoming.bin"
    payload = b"%PDF-1.7\nsource"
    source_path.write_bytes(payload)

    stored = storage.write_original(
        project_id="project-1",
        document_id="document-1",
        source_path=source_path,
    )
    assert stored.object_key == "controlled/raw/project-1/document-1/original.bin"
    assert stored.absolute_path.read_bytes() == payload

    metadata = {
        "schemaVersion": 1,
        "projectId": "project-1",
        "documentId": "document-1",
        "sha256": "abc",
    }
    source_meta = storage.write_source_metadata(
        project_id="project-1",
        document_id="document-1",
        metadata=metadata,
    )
    assert source_meta.object_key == "controlled/raw/project-1/document-1/source-meta.json"
    assert json.loads(source_meta.absolute_path.read_text(encoding="utf-8")) == metadata


def test_controlled_storage_rejects_overwrite_for_original_object(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)
    first_source = tmp_path / "first.bin"
    first_source.write_bytes(b"first")
    second_source = tmp_path / "second.bin"
    second_source.write_bytes(b"second")

    storage.write_original(
        project_id="project-1",
        document_id="document-1",
        source_path=first_source,
    )

    with pytest.raises(DocumentStorageError):
        storage.write_original(
            project_id="project-1",
            document_id="document-1",
            source_path=second_source,
        )

    persisted = tmp_path / "controlled/raw/project-1/document-1/original.bin"
    assert persisted.read_bytes() == b"first"


def test_controlled_storage_rejects_overwrite_for_source_meta(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)
    storage.write_source_metadata(
        project_id="project-1",
        document_id="document-1",
        metadata={"schemaVersion": 1},
    )

    with pytest.raises(DocumentStorageError):
        storage.write_source_metadata(
            project_id="project-1",
            document_id="document-1",
            metadata={"schemaVersion": 2},
        )


def test_upload_session_chunks_are_idempotent_and_assembled_in_order(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)

    first = storage.append_upload_session_chunk(
        project_id="project-1",
        session_id="session-1",
        chunk_index=0,
        payload=b"hello",
    )
    second = storage.append_upload_session_chunk(
        project_id="project-1",
        session_id="session-1",
        chunk_index=1,
        payload=b"-world",
    )
    duplicate = storage.append_upload_session_chunk(
        project_id="project-1",
        session_id="session-1",
        chunk_index=0,
        payload=b"hello",
    )

    assert first.read_bytes() == b"hello"
    assert second.read_bytes() == b"-world"
    assert duplicate == first

    assembled = storage.move_upload_session_into_original(
        project_id="project-1",
        document_id="document-assembled",
        session_id="session-1",
        last_chunk_index=1,
    )
    assert assembled.object_key == "controlled/raw/project-1/document-assembled/original.bin"
    assert assembled.absolute_path.read_bytes() == b"hello-world"


def test_upload_session_chunk_collision_and_missing_chunk_fail_closed(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)
    storage.append_upload_session_chunk(
        project_id="project-1",
        session_id="session-2",
        chunk_index=0,
        payload=b"A",
    )

    with pytest.raises(DocumentStorageError):
        storage.append_upload_session_chunk(
            project_id="project-1",
            session_id="session-2",
            chunk_index=0,
            payload=b"B",
        )

    with pytest.raises(DocumentStorageError):
        storage.move_upload_session_into_original(
            project_id="project-1",
            document_id="document-missing",
            session_id="session-2",
            last_chunk_index=1,
        )


def test_upload_session_chunk_cleanup_removes_session_directory(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)
    storage.append_upload_session_chunk(
        project_id="project-1",
        session_id="session-3",
        chunk_index=0,
        payload=b"chunk",
    )
    chunk_path = storage.resolve_upload_session_chunk_path(
        project_id="project-1",
        session_id="session-3",
        chunk_index=0,
    )
    assert chunk_path.exists()

    storage.clear_upload_session_chunks(project_id="project-1", session_id="session-3")
    assert not chunk_path.parent.parent.exists()


def test_preprocess_outputs_write_under_canonical_derived_prefix(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)

    gray = storage.write_preprocess_gray_image(
        project_id="project-1",
        document_id="document-1",
        run_id="run-1",
        page_index=0,
        payload=b"gray-bytes",
    )
    metrics = storage.write_preprocess_page_metrics(
        project_id="project-1",
        document_id="document-1",
        run_id="run-1",
        page_index=0,
        metrics_json={"contrast_score": 0.42, "warnings": ["LOW_DPI"]},
    )
    manifest = storage.write_preprocess_manifest(
        project_id="project-1",
        document_id="document-1",
        run_id="run-1",
        payload=b'{"manifest":true}\n',
    )

    assert (
        gray.object_key
        == "controlled/derived/project-1/document-1/preprocess/run-1/gray/0.png"
    )
    assert (
        metrics.object_key
        == "controlled/derived/project-1/document-1/preprocess/run-1/metrics/0.json"
    )
    assert (
        manifest.object_key
        == "controlled/derived/project-1/document-1/preprocess/run-1/manifest.json"
    )


def test_preprocess_output_writes_are_idempotent_for_retries(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)

    first = storage.write_preprocess_gray_image(
        project_id="project-1",
        document_id="document-2",
        run_id="run-2",
        page_index=1,
        payload=b"stable-gray",
    )
    duplicate = storage.write_preprocess_gray_image(
        project_id="project-1",
        document_id="document-2",
        run_id="run-2",
        page_index=1,
        payload=b"stable-gray",
    )
    assert first.object_key == duplicate.object_key

    with pytest.raises(DocumentStorageError):
        storage.write_preprocess_gray_image(
            project_id="project-1",
            document_id="document-2",
            run_id="run-2",
            page_index=1,
            payload=b"different-bytes",
        )


def test_preprocess_manifest_is_immutable_once_persisted(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)

    first = storage.write_preprocess_manifest(
        project_id="project-2",
        document_id="document-9",
        run_id="run-9",
        payload=b'{"schemaVersion":2}\n',
    )
    duplicate = storage.write_preprocess_manifest(
        project_id="project-2",
        document_id="document-9",
        run_id="run-9",
        payload=b'{"schemaVersion":2}\n',
    )
    assert duplicate.object_key == first.object_key

    with pytest.raises(DocumentStorageError):
        storage.write_preprocess_manifest(
            project_id="project-2",
            document_id="document-9",
            run_id="run-9",
            payload=b'{"schemaVersion":3}\n',
        )


def test_layout_outputs_write_under_canonical_derived_prefix(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)

    pagexml = storage.write_layout_page_xml(
        project_id="project-1",
        document_id="document-1",
        run_id="layout-run-1",
        page_index=0,
        payload=b"<PcGts />\n",
    )
    overlay = storage.write_layout_page_overlay(
        project_id="project-1",
        document_id="document-1",
        run_id="layout-run-1",
        page_index=0,
        payload=b'{"schemaVersion":1}\n',
    )
    manifest = storage.write_layout_manifest(
        project_id="project-1",
        document_id="document-1",
        run_id="layout-run-1",
        payload=b'{"schemaVersion":1,"pages":[]}\n',
    )
    thumbnail = storage.write_layout_page_thumbnail(
        project_id="project-1",
        document_id="document-1",
        run_id="layout-run-1",
        page_index=0,
        payload=b"thumb",
    )
    line_crop = storage.write_layout_line_crop(
        project_id="project-1",
        document_id="document-1",
        run_id="layout-run-1",
        page_index=0,
        line_id="line-1",
        payload=b"line",
    )
    region_crop = storage.write_layout_region_crop(
        project_id="project-1",
        document_id="document-1",
        run_id="layout-run-1",
        page_index=0,
        region_id="region-1",
        payload=b"region",
    )
    context = storage.write_layout_context_window(
        project_id="project-1",
        document_id="document-1",
        run_id="layout-run-1",
        page_index=0,
        line_id="line-1",
        payload=b'{"schemaVersion":1}\n',
    )

    assert (
        pagexml.object_key
        == "controlled/derived/project-1/document-1/layout/layout-run-1/page/0.xml"
    )
    assert (
        overlay.object_key
        == "controlled/derived/project-1/document-1/layout/layout-run-1/page/0.json"
    )
    assert (
        manifest.object_key
        == "controlled/derived/project-1/document-1/layout/layout-run-1/manifest.json"
    )
    assert (
        thumbnail.object_key
        == "controlled/derived/project-1/document-1/layout/layout-run-1/page/0/thumbnail.png"
    )
    assert (
        line_crop.object_key
        == "controlled/derived/project-1/document-1/layout/layout-run-1/page/0/lines/line-1.png"
    )
    assert (
        region_crop.object_key
        == "controlled/derived/project-1/document-1/layout/layout-run-1/page/0/regions/region-1.png"
    )
    assert (
        context.object_key
        == "controlled/derived/project-1/document-1/layout/layout-run-1/page/0/context/line-1.json"
    )


def test_layout_outputs_are_idempotent_for_same_payload(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)

    first = storage.write_layout_page_overlay(
        project_id="project-1",
        document_id="document-2",
        run_id="layout-run-2",
        page_index=1,
        payload=b'{"schemaVersion":1,"ok":true}\n',
    )
    second = storage.write_layout_page_overlay(
        project_id="project-1",
        document_id="document-2",
        run_id="layout-run-2",
        page_index=1,
        payload=b'{"schemaVersion":1,"ok":true}\n',
    )
    assert second.object_key == first.object_key

    with pytest.raises(DocumentStorageError):
        storage.write_layout_page_overlay(
            project_id="project-1",
            document_id="document-2",
            run_id="layout-run-2",
            page_index=1,
            payload=b'{"schemaVersion":2,"ok":true}\n',
        )


def test_transcription_outputs_write_under_canonical_derived_prefix(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)

    pagexml = storage.write_transcription_page_xml(
        project_id="project-1",
        document_id="document-1",
        run_id="transcription-run-1",
        page_index=0,
        payload=b"<PcGts />\n",
    )
    response = storage.write_transcription_raw_response(
        project_id="project-1",
        document_id="document-1",
        run_id="transcription-run-1",
        page_index=0,
        payload=b'{"schemaVersion":1}\n',
    )
    hocr = storage.write_transcription_hocr(
        project_id="project-1",
        document_id="document-1",
        run_id="transcription-run-1",
        page_index=0,
        payload=b"<html></html>\n",
    )

    assert (
        pagexml.object_key
        == "controlled/derived/project-1/document-1/transcription/transcription-run-1/page/0.xml"
    )
    assert (
        response.object_key
        == "controlled/derived/project-1/document-1/transcription/transcription-run-1/page/0.response.json"
    )
    assert (
        hocr.object_key
        == "controlled/derived/project-1/document-1/transcription/transcription-run-1/page/0.hocr"
    )


def test_transcription_raw_response_writes_are_idempotent_for_retries(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)

    first = storage.write_transcription_raw_response(
        project_id="project-1",
        document_id="document-2",
        run_id="transcription-run-2",
        page_index=1,
        payload=b'{"schemaVersion":1,"targets":[]}\n',
    )
    duplicate = storage.write_transcription_raw_response(
        project_id="project-1",
        document_id="document-2",
        run_id="transcription-run-2",
        page_index=1,
        payload=b'{"schemaVersion":1,"targets":[]}\n',
    )
    assert first.object_key == duplicate.object_key

    with pytest.raises(DocumentStorageError):
        storage.write_transcription_raw_response(
            project_id="project-1",
            document_id="document-2",
            run_id="transcription-run-2",
            page_index=1,
            payload=b'{"schemaVersion":2,"targets":[]}\n',
        )


def test_transcription_corrected_pagexml_key_scopes_by_transcript_version(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)

    base_key = storage.build_transcription_page_xml_key(
        project_id="project-1",
        document_id="document-1",
        run_id="transcription-run-1",
        page_index=0,
    )
    corrected_key = storage.build_transcription_corrected_page_xml_key(
        project_id="project-1",
        document_id="document-1",
        run_id="transcription-run-1",
        page_index=0,
        transcript_version_id="transcript-version-1",
    )

    assert (
        base_key
        == "controlled/derived/project-1/document-1/transcription/transcription-run-1/page/0.xml"
    )
    assert (
        corrected_key
        == "controlled/derived/project-1/document-1/transcription/transcription-run-1/versions/transcript-version-1/page/0.xml"
    )


def test_transcription_corrected_pagexml_write_is_idempotent_per_version(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    storage = DocumentStorage(settings=settings)

    first = storage.write_transcription_corrected_page_xml(
        project_id="project-1",
        document_id="document-2",
        run_id="transcription-run-2",
        page_index=1,
        transcript_version_id="transcript-version-1",
        payload=b"<PcGts><Page /></PcGts>\n",
    )
    duplicate = storage.write_transcription_corrected_page_xml(
        project_id="project-1",
        document_id="document-2",
        run_id="transcription-run-2",
        page_index=1,
        transcript_version_id="transcript-version-1",
        payload=b"<PcGts><Page /></PcGts>\n",
    )
    second_version = storage.write_transcription_corrected_page_xml(
        project_id="project-1",
        document_id="document-2",
        run_id="transcription-run-2",
        page_index=1,
        transcript_version_id="transcript-version-2",
        payload=b"<PcGts><Page /></PcGts>\n",
    )

    assert first.object_key == duplicate.object_key
    assert first.object_key != second_version.object_key

    with pytest.raises(DocumentStorageError):
        storage.write_transcription_corrected_page_xml(
            project_id="project-1",
            document_id="document-2",
            run_id="transcription-run-2",
            page_index=1,
            transcript_version_id="transcript-version-1",
            payload=b"<PcGts><Page><TextRegion /></Page></PcGts>\n",
        )
