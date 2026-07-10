from datetime import date

import httpx
import pytest
from langchain_core.documents import Document
from pypdf import PdfWriter

from bundesrag.dip.models import DocumentMeta
from bundesrag.ingestion import pipeline
from bundesrag.ingestion.manifest import PendingDocument, add_pending, load_pending
from bundesrag.ingestion.pipeline import (
    DownloadAborted,
    DownloadCounts,
    IndexCounts,
    OperationCancelled,
    run_delete_all,
    run_delete_file,
    run_download,
    run_index,
    run_status,
)
from bundesrag.query_agent.schema import DipQueryFilters


def _drucksache_meta(id_: str = "1") -> DocumentMeta:
    return DocumentMeta(
        id=id_,
        dokumentnummer=f"19/{id_}",
        datum=date(2026, 1, 5),
        wahlperiode=21,
        drucksachetyp="Antrag",
        titel="Ein Titel",
        pdf_url=f"https://example.org/{id_}.pdf",
    )


@pytest.fixture
def query_agent(mocker):
    agent = mocker.Mock()
    agent.build_query.return_value = DipQueryFilters(endpoint="drucksache", wahlperiode=21)
    return agent


def _fake_download_pdf(url, dest):
    # Create the file like the real download does — index/status treat a
    # pending entry without a PDF on disk as manually deleted and prune it.
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"%PDF-1.4")
    return dest


@pytest.fixture
def dip_client(mocker):
    client = mocker.Mock()
    client.list_drucksachen.return_value = [_drucksache_meta("1")]
    client.list_plenarprotokolle.return_value = []
    client.download_pdf.side_effect = _fake_download_pdf
    return client


@pytest.fixture
def vectorstore(mocker):
    store = mocker.Mock()
    store.get.return_value = {"ids": [], "metadatas": []}
    return store


@pytest.fixture(autouse=True)
def fake_chunking(mocker):
    mocker.patch.object(
        pipeline,
        "load_pdf_as_chunks",
        return_value=[Document(page_content="text", metadata={"id": "19/1-p1-0"})],
    )


def test_run_download_happy_path(settings, query_agent, dip_client):
    summary = run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )

    assert summary.num_documents == 1
    dip_client.download_pdf.assert_called_once()
    pending = load_pending(settings)
    assert len(pending) == 1
    assert pending[0].kind == "drucksache"


def test_run_download_passes_filters_to_drucksache_listing(settings, query_agent, dip_client):
    query_agent.build_query.return_value = DipQueryFilters(
        endpoint="drucksache",
        datum_start=date(2026, 1, 1),
        ressort_fdf=["Bundesministerium für Forschung, Technologie und Raumfahrt"],
    )

    run_download(
        "Drucksachen des BMFTR seit dem 01.01.2026.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )

    _, kwargs = dip_client.list_drucksachen.call_args
    assert kwargs["datum_start"] == date(2026, 1, 1)
    assert kwargs["ressort_fdf"] == ["Bundesministerium für Forschung, Technologie und Raumfahrt"]


def test_run_download_skips_documents_that_fail_to_download(settings, query_agent, dip_client):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]

    def download_pdf(url, dest):
        if "1" in url:
            request = httpx.Request("GET", url)
            raise httpx.HTTPStatusError("not found", request=request, response=None)
        return dest

    dip_client.download_pdf.side_effect = download_pdf

    summary = run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )

    assert summary.num_documents == 1
    assert summary.num_failed == 1
    pending = load_pending(settings)
    assert len(pending) == 1
    assert pending[0].meta["id"] == "2"


def test_run_download_counts_documents_without_pdf_url_as_failed(settings, query_agent, dip_client):
    meta_without_pdf = _drucksache_meta("1").model_copy(update={"pdf_url": None})
    dip_client.list_drucksachen.return_value = [meta_without_pdf, _drucksache_meta("2")]

    summary = run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )

    assert summary.num_documents == 1
    assert summary.num_failed == 1
    pending = load_pending(settings)
    assert len(pending) == 1
    assert pending[0].meta["id"] == "2"


def test_run_download_reports_progress_per_document(settings, query_agent, dip_client):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]
    progress = []

    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
        on_progress=lambda current, total: progress.append((current, total)),
    )

    assert progress == [(0, 2), (1, 2), (2, 2)]


def test_run_download_reports_progress_for_failed_documents_too(settings, query_agent, dip_client):
    meta_without_pdf = _drucksache_meta("1").model_copy(update={"pdf_url": None})
    dip_client.list_drucksachen.return_value = [meta_without_pdf, _drucksache_meta("2")]
    progress = []

    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
        on_progress=lambda current, total: progress.append((current, total)),
    )

    assert progress == [(0, 2), (1, 2), (2, 2)]


def test_run_download_skips_already_downloaded_documents(settings, query_agent, dip_client):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]
    existing_pdf = settings.pdf_dir / "drucksache" / "19_1.pdf"
    existing_pdf.parent.mkdir(parents=True, exist_ok=True)
    existing_pdf.write_bytes(b"%PDF-1.4")
    confirm_calls = []

    def confirm_count(counts: DownloadCounts) -> int:
        confirm_calls.append(counts)
        return counts.num_to_download

    summary = run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=confirm_count,
        confirm_filters=lambda f: True,
    )

    assert confirm_calls == [DownloadCounts(num_matched=2, num_existing=1, num_to_download=1)]
    assert summary.num_documents == 1
    assert summary.num_skipped == 1
    assert summary.num_failed == 0
    dip_client.download_pdf.assert_called_once()
    pending = load_pending(settings)
    assert [entry.meta["id"] for entry in pending] == ["2"]


def test_run_download_skips_count_confirmation_when_all_documents_exist(
    settings, query_agent, dip_client
):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]
    for name in ("19_1.pdf", "19_2.pdf"):
        existing_pdf = settings.pdf_dir / "drucksache" / name
        existing_pdf.parent.mkdir(parents=True, exist_ok=True)
        existing_pdf.write_bytes(b"%PDF-1.4")

    summary = run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: pytest.fail("confirm_count must not be called"),
        confirm_filters=lambda f: True,
    )

    assert summary.num_documents == 0
    assert summary.num_skipped == 2
    dip_client.download_pdf.assert_not_called()


def test_run_download_uses_plenarprotokoll_listing(settings, query_agent, dip_client):
    query_agent.build_query.return_value = DipQueryFilters(
        endpoint="plenarprotokoll", wahlperiode=21
    )
    dip_client.list_plenarprotokolle.return_value = [
        DocumentMeta(
            id="1",
            dokumentnummer="21/1",
            datum=date(2026, 1, 5),
            wahlperiode=21,
            titel="Protokoll der 1. Sitzung",
            pdf_url="https://example.org/21_1.pdf",
        )
    ]

    summary = run_download(
        "Plenarprotokolle der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )

    dip_client.list_drucksachen.assert_not_called()
    assert summary.num_documents == 1


def test_run_download_asks_for_confirmation_every_time(settings, query_agent, dip_client):
    confirm_calls = []

    def confirm_count(counts: DownloadCounts) -> int:
        confirm_calls.append(counts)
        return counts.num_to_download

    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=confirm_count,
        confirm_filters=lambda f: True,
    )

    assert confirm_calls == [DownloadCounts(num_matched=1, num_existing=0, num_to_download=1)]


def test_run_download_aborts_when_user_enters_zero(settings, query_agent, dip_client):
    with pytest.raises(DownloadAborted):
        run_download(
            "Drucksachen der 21. Wahlperiode.",
            settings,
            query_agent=query_agent,
            dip_client=dip_client,
            ask_user=lambda q: "",
            confirm_count=lambda counts: 0,
            confirm_filters=lambda f: True,
        )

    dip_client.download_pdf.assert_not_called()
    assert load_pending(settings) == []


def test_run_download_limits_to_most_recent_documents(settings, query_agent, dip_client):
    dip_client.list_drucksachen.return_value = [
        DocumentMeta(
            id=id_,
            dokumentnummer=f"19/{id_}",
            datum=date(2026, 1, day),
            wahlperiode=21,
            drucksachetyp="Antrag",
            titel="Ein Titel",
            pdf_url=f"https://example.org/{id_}.pdf",
        )
        for id_, day in (("1", 1), ("2", 10), ("3", 5))
    ]

    summary = run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: 1,
        confirm_filters=lambda f: True,
    )

    assert summary.num_documents == 1
    pending = load_pending(settings)
    assert pending[0].meta["id"] == "2"


def test_run_download_count_limit_applies_to_not_yet_downloaded_documents(
    settings, query_agent, dip_client
):
    dip_client.list_drucksachen.return_value = [
        DocumentMeta(
            id=id_,
            dokumentnummer=f"19/{id_}",
            datum=date(2026, 1, day),
            wahlperiode=21,
            drucksachetyp="Antrag",
            titel="Ein Titel",
            pdf_url=f"https://example.org/{id_}.pdf",
        )
        for id_, day in (("1", 1), ("2", 10), ("3", 5))
    ]
    # The most recent match already exists, so the limit of 1 must pick the
    # most recent of the remaining documents instead.
    existing_pdf = settings.pdf_dir / "drucksache" / "19_2.pdf"
    existing_pdf.parent.mkdir(parents=True, exist_ok=True)
    existing_pdf.write_bytes(b"%PDF-1.4")

    summary = run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: 1,
        confirm_filters=lambda f: True,
    )

    assert summary.num_documents == 1
    assert summary.num_skipped == 1
    pending = load_pending(settings)
    assert [entry.meta["id"] for entry in pending] == ["3"]


def test_run_download_cancel_keeps_completed_downloads_pending(settings, query_agent, dip_client):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]

    with pytest.raises(OperationCancelled):
        run_download(
            "Drucksachen der 21. Wahlperiode.",
            settings,
            query_agent=query_agent,
            dip_client=dip_client,
            ask_user=lambda q: "",
            confirm_count=lambda counts: counts.num_to_download,
            confirm_filters=lambda f: True,
            should_cancel=lambda: dip_client.download_pdf.call_count >= 1,
        )

    dip_client.download_pdf.assert_called_once()
    pending = load_pending(settings)
    assert [entry.meta["id"] for entry in pending] == ["1"]


def test_run_download_interrupted_run_still_records_pending(settings, query_agent, dip_client):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]

    def download_pdf(url, dest):
        if "2.pdf" in url:
            raise KeyboardInterrupt
        return dest

    dip_client.download_pdf.side_effect = download_pdf

    with pytest.raises(KeyboardInterrupt):
        run_download(
            "Drucksachen der 21. Wahlperiode.",
            settings,
            query_agent=query_agent,
            dip_client=dip_client,
            ask_user=lambda q: "",
            confirm_count=lambda counts: counts.num_to_download,
            confirm_filters=lambda f: True,
        )

    # The document downloaded before the interrupt must be queued for
    # indexing, or later runs would skip it without ever indexing it.
    pending = load_pending(settings)
    assert [entry.meta["id"] for entry in pending] == ["1"]


def test_run_index_happy_path(settings, query_agent, dip_client, vectorstore):
    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )

    summary = run_index(settings, vectorstore=vectorstore)

    assert summary.num_documents == 1
    assert summary.num_chunks == 1
    vectorstore.add_documents.assert_called_once()
    assert load_pending(settings) == []


def test_run_index_leaves_remaining_documents_pending_on_failure(
    settings, query_agent, dip_client, vectorstore
):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]
    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )

    vectorstore.add_documents.side_effect = [None, RuntimeError("boom")]

    with pytest.raises(RuntimeError):
        run_index(settings, vectorstore=vectorstore)

    pending = load_pending(settings)
    assert len(pending) == 1
    assert pending[0].meta["id"] == "2"


def test_run_index_reports_progress_per_document(settings, query_agent, dip_client, vectorstore):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]
    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )
    progress = []

    run_index(
        settings,
        vectorstore=vectorstore,
        on_progress=lambda current, total: progress.append((current, total)),
    )

    assert progress == [(0, 2), (1, 2), (2, 2)]


def test_run_index_reports_counts(settings, query_agent, dip_client, vectorstore):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]
    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )
    # Index the first document, then fail, so one document stays pending.
    vectorstore.add_documents.side_effect = [None, RuntimeError("boom")]
    with pytest.raises(RuntimeError):
        run_index(settings, vectorstore=vectorstore)
    vectorstore.add_documents.side_effect = None
    counts = []

    run_index(settings, vectorstore=vectorstore, on_counts=counts.append)

    assert counts == [IndexCounts(num_to_index=1, num_indexed=1)]


def test_run_index_cancel_leaves_remaining_documents_pending(
    settings, query_agent, dip_client, vectorstore
):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]
    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )

    with pytest.raises(OperationCancelled):
        run_index(
            settings,
            vectorstore=vectorstore,
            should_cancel=lambda: vectorstore.add_documents.call_count >= 1,
        )

    vectorstore.add_documents.assert_called_once()
    pending = load_pending(settings)
    assert [entry.meta["id"] for entry in pending] == ["2"]


def test_run_index_skips_pending_documents_whose_pdf_was_deleted(
    settings, query_agent, dip_client, vectorstore
):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]
    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )
    (settings.pdf_dir / "drucksache" / "19_1.pdf").unlink()
    counts = []

    summary = run_index(settings, vectorstore=vectorstore, on_counts=counts.append)

    assert summary.num_documents == 1
    assert counts == [IndexCounts(num_to_index=1, num_indexed=0)]
    assert load_pending(settings) == []


def test_run_index_without_pending_documents_is_a_noop(settings, vectorstore):
    summary = run_index(settings, vectorstore=vectorstore)

    assert summary.num_documents == 0
    assert summary.num_chunks == 0
    vectorstore.add_documents.assert_not_called()


def test_run_delete_all_removes_pdfs_resets_vectorstore_and_manifest(
    settings, query_agent, dip_client, vectorstore
):
    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    summary = run_delete_all(settings, vectorstore=vectorstore)

    assert summary.num_files == 1
    assert not pdf_path.exists()
    vectorstore.delete_collection.assert_called_once()
    assert load_pending(settings) == []


def test_run_delete_all_without_downloads_is_a_noop_on_files(settings, vectorstore):
    summary = run_delete_all(settings, vectorstore=vectorstore)

    assert summary.num_files == 0
    vectorstore.delete_collection.assert_called_once()


def test_run_delete_file_removes_pdf_and_chunks(settings, vectorstore):
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    run_delete_file(pdf_path, settings, vectorstore=vectorstore)

    assert not pdf_path.exists()
    vectorstore.delete.assert_called_once_with(where={"pdf_path": str(pdf_path)})


def test_run_delete_file_removes_pending_manifest_entry(
    settings, query_agent, dip_client, vectorstore
):
    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    assert load_pending(settings)

    run_delete_file(pdf_path, settings, vectorstore=vectorstore)

    assert not pdf_path.exists()
    assert load_pending(settings) == []


def test_run_delete_file_unknown_path_raises(settings, vectorstore):
    with pytest.raises(FileNotFoundError):
        run_delete_file(
            settings.pdf_dir / "drucksache" / "19_1.pdf", settings, vectorstore=vectorstore
        )

    vectorstore.delete.assert_not_called()


def test_run_delete_file_refuses_paths_outside_pdf_dir(settings, vectorstore, tmp_path):
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4")

    with pytest.raises(FileNotFoundError):
        run_delete_file(outside, settings, vectorstore=vectorstore)

    assert outside.exists()
    vectorstore.delete.assert_not_called()


def test_run_status_reports_downloaded_and_indexed_counts(
    settings, query_agent, dip_client, vectorstore
):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]
    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )
    for pdf_path in (
        settings.pdf_dir / "drucksache" / "19_1.pdf",
        settings.pdf_dir / "drucksache" / "19_2.pdf",
    ):
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-1.4")

    vectorstore.add_documents.side_effect = [None, RuntimeError("boom")]
    with pytest.raises(RuntimeError):
        run_index(settings, vectorstore=vectorstore)

    summary = run_status(settings, vectorstore=vectorstore)

    assert summary.num_downloaded == 2
    assert summary.num_indexed == 1
    statuses = {file.pdf_path.name: file.indexed for file in summary.files}
    assert statuses == {"19_1.pdf": True, "19_2.pdf": False}


def test_run_status_reports_sizes_chunk_count_and_per_document_metadata(settings, vectorstore):
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    (settings.chroma_dir / "chroma.sqlite3").write_bytes(b"0" * 10)

    def chunk_meta(page, chunk_index):
        return {
            "id": f"19/1-p{page}-{chunk_index}",
            "doc_id": "1",
            "dokumentnummer": "19/1",
            "citation_label": "Ein Titel",
            "datum": "2026-01-05",
            "page": page,
            "pdf_path": str(pdf_path),
            "source_url": "https://example.org/1.pdf",
        }

    metadatas = [chunk_meta(1, 0), chunk_meta(1, 1), chunk_meta(2, 0)]
    vectorstore.get.return_value = {
        "ids": [meta["id"] for meta in metadatas],
        "metadatas": metadatas,
    }

    summary = run_status(settings, vectorstore=vectorstore)

    assert summary.num_chunks == 3
    assert summary.pdf_size_bytes == len(b"%PDF-1.4")
    assert summary.vectorstore_size_bytes == 10
    assert summary.files[0].kind == "drucksache"
    info = summary.files[0].info
    assert info is not None
    assert info.doc_id == "1"
    assert info.dokumentnummer == "19/1"
    assert info.citation_label == "Ein Titel"
    assert info.datum == "2026-01-05"
    assert info.source_url == "https://example.org/1.pdf"
    assert info.num_chunks == 3
    assert info.num_pages == 2


def test_run_status_leaves_info_empty_when_neither_indexed_nor_pending(settings, vectorstore):
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    summary = run_status(settings, vectorstore=vectorstore)

    assert summary.num_chunks == 0
    assert summary.files[0].info is None


def test_run_status_reports_pending_document_info_from_manifest(settings, vectorstore):
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as stream:
        writer.write(stream)
    add_pending(
        settings,
        [
            PendingDocument(
                kind="drucksache",
                pdf_path=pdf_path,
                meta=_drucksache_meta("1").model_dump(mode="json"),
            )
        ],
    )

    summary = run_status(settings, vectorstore=vectorstore)

    file = summary.files[0]
    assert file.indexed is False
    assert file.info is not None
    assert file.info.doc_id == "1"
    assert file.info.dokumentnummer == "19/1"
    assert file.info.citation_label == "Ein Titel"
    assert file.info.datum == "2026-01-05"
    assert file.info.source_url == "https://example.org/1.pdf"
    assert file.info.num_chunks is None
    assert file.info.num_pages == 2


def test_run_status_tolerates_unparseable_pdf_for_pending_page_count(settings, vectorstore):
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4 truncated")
    add_pending(
        settings,
        [
            PendingDocument(
                kind="drucksache",
                pdf_path=pdf_path,
                meta=_drucksache_meta("1").model_dump(mode="json"),
            )
        ],
    )

    summary = run_status(settings, vectorstore=vectorstore)

    assert summary.files[0].info is not None
    assert summary.files[0].info.num_pages is None


def test_run_status_prunes_pending_entries_whose_pdf_was_deleted(
    settings, query_agent, dip_client, vectorstore
):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1"),
        _drucksache_meta("2"),
    ]
    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda counts: counts.num_to_download,
        confirm_filters=lambda f: True,
    )
    (settings.pdf_dir / "drucksache" / "19_1.pdf").unlink()

    summary = run_status(settings, vectorstore=vectorstore)

    assert summary.num_downloaded == 1
    assert summary.num_indexed == 0
    assert [entry.meta["id"] for entry in load_pending(settings)] == ["2"]


def test_run_status_without_downloads_is_empty(settings, vectorstore):
    summary = run_status(settings, vectorstore=vectorstore)

    assert summary.num_downloaded == 0
    assert summary.num_indexed == 0
    assert summary.files == []
    assert summary.num_chunks == 0
    assert summary.pdf_size_bytes == 0
    assert summary.vectorstore_size_bytes == 0
