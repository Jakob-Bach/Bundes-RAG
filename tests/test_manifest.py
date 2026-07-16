from pathlib import Path

from bundesrag.ingestion.manifest import (
    DocumentInfo,
    PendingDocument,
    add_indexed_info,
    add_pending,
    indexed_info_path,
    load_indexed_info,
    load_pending,
    remove_indexed_info,
    remove_pending,
)


def _pending(pdf_path: str, doc_id: str) -> PendingDocument:
    return PendingDocument(kind="drucksache", pdf_path=Path(pdf_path), meta={"id": doc_id})


def _info(doc_id: str) -> DocumentInfo:
    return DocumentInfo(
        doc_id=doc_id,
        dokumentnummer=f"19/{doc_id}",
        citation_label="Ein Titel",
        datum="2026-01-05",
        source_url=f"https://example.org/{doc_id}.pdf",
        num_chunks=3,
        num_pages=2,
    )


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


def test_add_pending_deduplicates_by_pdf_path_keeping_newest(settings):
    add_pending(settings, [_pending("a.pdf", "1"), _pending("b.pdf", "2")])
    add_pending(settings, [_pending("a.pdf", "1-neu")])

    pending = load_pending(settings)
    assert [entry.meta["id"] for entry in pending] == ["1-neu", "2"]


def test_remove_pending_removes_only_matching_entry(settings):
    add_pending(settings, [_pending("a.pdf", "1"), _pending("b.pdf", "2")])

    remove_pending(settings, Path("a.pdf"))

    pending = load_pending(settings)
    assert [entry.meta["id"] for entry in pending] == ["2"]


def test_load_indexed_info_without_manifest_file_returns_empty_dict(settings):
    assert load_indexed_info(settings) == {}


def test_load_indexed_info_tolerates_corrupt_file(settings):
    # The indexed-docs manifest is derived data (run_status backfills it from
    # the vector store), so a corrupt file must not fail the caller.
    path = indexed_info_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("﻿not json", encoding="utf-8")

    assert load_indexed_info(settings) == {}


def test_add_indexed_info_round_trips_entries(settings):
    add_indexed_info(settings, Path("a.pdf"), _info("1"))
    add_indexed_info(settings, Path("b.pdf"), _info("2"))

    info_by_path = load_indexed_info(settings)
    assert set(info_by_path) == {Path("a.pdf"), Path("b.pdf")}
    assert info_by_path[Path("a.pdf")] == _info("1")


def test_add_indexed_info_overwrites_existing_entry(settings):
    add_indexed_info(settings, Path("a.pdf"), _info("1"))
    add_indexed_info(settings, Path("a.pdf"), _info("1-neu"))

    info_by_path = load_indexed_info(settings)
    assert info_by_path[Path("a.pdf")].doc_id == "1-neu"


def test_remove_indexed_info_removes_only_matching_entry(settings):
    add_indexed_info(settings, Path("a.pdf"), _info("1"))
    add_indexed_info(settings, Path("b.pdf"), _info("2"))

    remove_indexed_info(settings, Path("a.pdf"))

    assert set(load_indexed_info(settings)) == {Path("b.pdf")}
