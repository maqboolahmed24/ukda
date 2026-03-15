from __future__ import annotations

from datetime import UTC, datetime

from app.documents.service import DocumentService


def test_filter_manifest_entries_respects_category_page_review_and_time() -> None:
    entries = [
        {
            "entryId": "a",
            "category": "EMAIL",
            "pageIndex": 1,
            "reviewState": "APPROVED",
            "decisionTimestamp": "2026-03-14T09:00:00+00:00",
        },
        {
            "entryId": "b",
            "category": "PHONE",
            "pageIndex": 2,
            "reviewState": "OVERRIDDEN",
            "decisionTimestamp": "2026-03-14T11:00:00+00:00",
        },
    ]
    filtered = DocumentService._filter_manifest_entries(
        entries=entries,
        category="phone",
        page=2,
        review_state="overridden",
        from_timestamp=datetime(2026, 3, 14, 10, 0, tzinfo=UTC),
        to_timestamp=datetime(2026, 3, 14, 12, 0, tzinfo=UTC),
    )
    assert [item["entryId"] for item in filtered] == ["b"]
