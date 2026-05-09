"""
TMX-3702-v1 — backend contract: SegmentResponse exposes element_meta.

`Segment.element_meta` is the JSON column that carries DOCX revisions
metadata captured by TMX-3700. Without serialiser support, the data is
dark to the reviewer surface. This test pins the contract.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.core.tenant_context import org_context
from app.models.database import (
    DEFAULT_ORG_ID,
    Document,
    DocumentStatus,
    Segment,
    SegmentStatus,
)


client = TestClient(app)


@pytest.fixture
def seeded_doc_with_revisions():
    """Document + segments where one carries DOCX revision metadata."""
    doc_id = f"doc-{uuid.uuid4()}"
    seg_with_id = f"seg-{uuid.uuid4()}"
    seg_without_id = f"seg-{uuid.uuid4()}"
    now = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        doc = Document(
            id=doc_id,
            organization_id=DEFAULT_ORG_ID,
            name="rev-test.docx",
            file_type="docx",
            status=DocumentStatus.UPLOADED.value,
            source_language="en",
            target_language="de",
            created_at=now,
            updated_at=now,
        )
        seg_with = Segment(
            id=seg_with_id,
            organization_id=DEFAULT_ORG_ID,
            document_id=doc_id,
            order_index=1,
            source_text="Take the medication twice daily",
            element_type="Paragraph",
            element_meta={
                "revisions": {
                    "has_insertions": True,
                    "has_deletions": False,
                    "has_moves": False,
                    "authors": ["Dr. Reviewer"],
                    "dates": ["2026-04-01T10:00:00Z"],
                },
            },
            status=SegmentStatus.PENDING.value,
            created_at=now,
            updated_at=now,
        )
        seg_without = Segment(
            id=seg_without_id,
            organization_id=DEFAULT_ORG_ID,
            document_id=doc_id,
            order_index=2,
            source_text="No tracked changes here",
            element_type="Paragraph",
            element_meta=None,
            status=SegmentStatus.PENDING.value,
            created_at=now,
            updated_at=now,
        )
        session.add_all([doc, seg_with, seg_without])
        session.commit()
        yield {
            "doc_id": doc_id,
            "seg_with_id": seg_with_id,
            "seg_without_id": seg_without_id,
        }
    finally:
        with org_context(DEFAULT_ORG_ID):
            session.query(Segment).filter(Segment.document_id == doc_id).delete()
            session.query(Document).filter(Document.id == doc_id).delete()
            session.commit()
        session.close()


def test_list_segments_includes_element_meta_with_revisions(seeded_doc_with_revisions):
    res = client.get(f"/api/documents/{seeded_doc_with_revisions['doc_id']}/segments")
    assert res.status_code == 200
    items = res.json()
    seg_with = next(s for s in items if s["id"] == seeded_doc_with_revisions["seg_with_id"])
    assert "element_meta" in seg_with, "element_meta must be present on every segment response"
    assert seg_with["element_meta"] is not None
    revisions = seg_with["element_meta"]["revisions"]
    assert revisions["has_insertions"] is True
    assert revisions["has_deletions"] is False
    assert revisions["authors"] == ["Dr. Reviewer"]
    assert revisions["dates"] == ["2026-04-01T10:00:00Z"]


def test_list_segments_returns_null_element_meta_when_absent(seeded_doc_with_revisions):
    res = client.get(f"/api/documents/{seeded_doc_with_revisions['doc_id']}/segments")
    items = res.json()
    seg_without = next(s for s in items if s["id"] == seeded_doc_with_revisions["seg_without_id"])
    assert "element_meta" in seg_without, "element_meta key must be present even when null"
    assert seg_without["element_meta"] is None


def test_get_segment_includes_element_meta(seeded_doc_with_revisions):
    res = client.get(f"/api/segments/{seeded_doc_with_revisions['seg_with_id']}")
    assert res.status_code == 200
    body = res.json()
    assert body["element_meta"]["revisions"]["has_insertions"] is True
