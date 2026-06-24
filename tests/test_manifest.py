from pathlib import Path

from bundesrag.ingestion.manifest import (
    PendingDocument,
    add_pending,
    load_pending,
    remove_pending,
)


def _pending(pdf_path: str, doc_id: str) -> PendingDocument:
    return PendingDocument(kind="drucksache", pdf_path=Path(pdf_path), meta={"id": doc_id})


def test_load_pending_without_manifest_file_returns_empty_list(settings):
    assert load_pending(settings) == []


def test_add_pending_persists_entries(settings):
    add_pending(settings, [_pending("a.pdf", "1"), _pending("b.pdf", "2")])

    pending = load_pending(settings)
    assert [entry.meta["id"] for entry in pending] == ["1", "2"]


def test_add_pending_appends_to_existing_entries(settings):
    add_pending(settings, [_pending("a.pdf", "1")])
    add_pending(settings, [_pending("b.pdf", "2")])

    pending = load_pending(settings)
    assert [entry.meta["id"] for entry in pending] == ["1", "2"]


def test_remove_pending_removes_only_matching_entry(settings):
    add_pending(settings, [_pending("a.pdf", "1"), _pending("b.pdf", "2")])

    remove_pending(settings, Path("a.pdf"))

    pending = load_pending(settings)
    assert [entry.meta["id"] for entry in pending] == ["2"]
