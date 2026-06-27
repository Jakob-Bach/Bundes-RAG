from datetime import date

import pytest
from langchain_core.documents import Document

from bundesrag.dip.models import DrucksacheMeta, Fundstelle, PlenarprotokollMeta
from bundesrag.ingestion import pipeline
from bundesrag.ingestion.manifest import load_pending
from bundesrag.ingestion.pipeline import (
    DownloadAborted,
    run_delete_all,
    run_download,
    run_index,
    run_status,
)
from bundesrag.query_agent.schema import DipQueryFilters


def _drucksache_meta(id_: str = "1") -> DrucksacheMeta:
    return DrucksacheMeta(
        id=id_,
        dokumentnummer=f"19/{id_}",
        datum=date(2026, 1, 5),
        wahlperiode=21,
        drucksachetyp="Antrag",
        titel="Ein Titel",
        fundstelle=Fundstelle(
            id=id_, dokumentart="Drucksache", pdf_url=f"https://example.org/{id_}.pdf"
        ),
    )


@pytest.fixture
def query_agent(mocker):
    agent = mocker.Mock()
    agent.build_query.return_value = DipQueryFilters(endpoint="drucksache", wahlperiode=21)
    return agent


@pytest.fixture
def dip_client(mocker):
    client = mocker.Mock()
    client.list_drucksachen.return_value = [_drucksache_meta("1")]
    client.list_plenarprotokolle.return_value = []
    client.download_pdf.side_effect = lambda url, dest: dest
    return client


@pytest.fixture
def vectorstore(mocker):
    return mocker.Mock()


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
        confirm_count=lambda count: count,
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
        confirm_count=lambda count: count,
        confirm_filters=lambda f: True,
    )

    _, kwargs = dip_client.list_drucksachen.call_args
    assert kwargs["datum_start"] == date(2026, 1, 1)
    assert kwargs["ressort_fdf"] == ["Bundesministerium für Forschung, Technologie und Raumfahrt"]


def test_run_download_uses_plenarprotokoll_listing(settings, query_agent, dip_client):
    query_agent.build_query.return_value = DipQueryFilters(
        endpoint="plenarprotokoll", wahlperiode=21
    )
    dip_client.list_plenarprotokolle.return_value = [
        PlenarprotokollMeta(
            id="1",
            dokumentnummer="21/1",
            datum=date(2026, 1, 5),
            wahlperiode=21,
            titel="Protokoll der 1. Sitzung",
            fundstelle=Fundstelle(
                id="1",
                dokumentart="Plenarprotokoll",
                pdf_url="https://example.org/21_1.pdf",
            ),
        )
    ]

    summary = run_download(
        "Plenarprotokolle der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda count: count,
        confirm_filters=lambda f: True,
    )

    dip_client.list_drucksachen.assert_not_called()
    assert summary.num_documents == 1


def test_run_download_asks_for_confirmation_every_time(settings, query_agent, dip_client):
    confirm_calls = []

    def confirm_count(count: int) -> int:
        confirm_calls.append(count)
        return count

    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=confirm_count,
        confirm_filters=lambda f: True,
    )

    assert confirm_calls == [1]


def test_run_download_aborts_when_user_enters_zero(settings, query_agent, dip_client):
    with pytest.raises(DownloadAborted):
        run_download(
            "Drucksachen der 21. Wahlperiode.",
            settings,
            query_agent=query_agent,
            dip_client=dip_client,
            ask_user=lambda q: "",
            confirm_count=lambda count: 0,
            confirm_filters=lambda f: True,
        )

    dip_client.download_pdf.assert_not_called()
    assert load_pending(settings) == []


def test_run_download_limits_to_most_recent_documents(settings, query_agent, dip_client):
    dip_client.list_drucksachen.return_value = [
        DrucksacheMeta(
            id=id_,
            dokumentnummer=f"19/{id_}",
            datum=date(2026, 1, day),
            wahlperiode=21,
            drucksachetyp="Antrag",
            titel="Ein Titel",
            fundstelle=Fundstelle(
                id=id_, dokumentart="Drucksache", pdf_url=f"https://example.org/{id_}.pdf"
            ),
        )
        for id_, day in (("1", 1), ("2", 10), ("3", 5))
    ]

    summary = run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda count: 1,
        confirm_filters=lambda f: True,
    )

    assert summary.num_documents == 1
    pending = load_pending(settings)
    assert pending[0].meta["id"] == "2"


def test_run_index_happy_path(settings, query_agent, dip_client, vectorstore):
    run_download(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        ask_user=lambda q: "",
        confirm_count=lambda count: count,
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
        confirm_count=lambda count: count,
        confirm_filters=lambda f: True,
    )

    vectorstore.add_documents.side_effect = [None, RuntimeError("boom")]

    with pytest.raises(RuntimeError):
        run_index(settings, vectorstore=vectorstore)

    pending = load_pending(settings)
    assert len(pending) == 1
    assert pending[0].meta["id"] == "2"


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
        confirm_count=lambda count: count,
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
        confirm_count=lambda count: count,
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

    summary = run_status(settings)

    assert summary.num_downloaded == 2
    assert summary.num_indexed == 1
    statuses = {file.pdf_path.name: file.indexed for file in summary.files}
    assert statuses == {"19_1.pdf": True, "19_2.pdf": False}


def test_run_status_without_downloads_is_empty(settings):
    summary = run_status(settings)

    assert summary.num_downloaded == 0
    assert summary.num_indexed == 0
    assert summary.files == []
