from datetime import date
from pathlib import Path

import pytest
from langchain_core.documents import Document

from bundesrag.dip.models import DrucksacheMeta, Fundstelle, PlenarprotokollMeta
from bundesrag.ingestion import pipeline
from bundesrag.ingestion.pipeline import FetchAborted, run_fetch
from bundesrag.query_agent.schema import DipQueryFilters


def _drucksache_meta(id_: str = "1") -> DrucksacheMeta:
    return DrucksacheMeta(
        id=id_,
        dokumentnummer=f"19/{id_}",
        datum=date(2026, 1, 5),
        wahlperiode=21,
        drucksachetyp="Antrag",
        titel="Ein Titel",
        fundstelle=Fundstelle(id=id_, dokumentart="Drucksache", pdf_url=f"https://example.org/{id_}.pdf"),
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


def test_run_fetch_happy_path(settings, query_agent, dip_client, vectorstore):
    summary = run_fetch(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        vectorstore=vectorstore,
        ask_user=lambda q: "",
    )

    assert summary.num_documents == 1
    assert summary.num_chunks == 1
    dip_client.download_pdf.assert_called_once()
    vectorstore.add_documents.assert_called_once()


def test_run_fetch_passes_filters_to_drucksache_listing(settings, query_agent, dip_client, vectorstore):
    query_agent.build_query.return_value = DipQueryFilters(
        endpoint="drucksache",
        datum_start=date(2026, 1, 1),
        ressort_fdf=["Bundesministerium für Forschung, Technologie und Raumfahrt"],
    )

    run_fetch(
        "Drucksachen des BMFTR seit dem 01.01.2026.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        vectorstore=vectorstore,
        ask_user=lambda q: "",
    )

    _, kwargs = dip_client.list_drucksachen.call_args
    assert kwargs["datum_start"] == date(2026, 1, 1)
    assert kwargs["ressort_fdf"] == ["Bundesministerium für Forschung, Technologie und Raumfahrt"]


def test_run_fetch_uses_plenarprotokoll_listing(settings, query_agent, dip_client, vectorstore):
    query_agent.build_query.return_value = DipQueryFilters(endpoint="plenarprotokoll", wahlperiode=21)
    dip_client.list_plenarprotokolle.return_value = [
        PlenarprotokollMeta(
            id="1",
            dokumentnummer="21/1",
            datum=date(2026, 1, 5),
            wahlperiode=21,
            titel="Protokoll der 1. Sitzung",
            fundstelle=Fundstelle(id="1", dokumentart="Plenarprotokoll", pdf_url="https://example.org/21_1.pdf"),
        )
    ]

    summary = run_fetch(
        "Plenarprotokolle der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        vectorstore=vectorstore,
        ask_user=lambda q: "",
    )

    dip_client.list_drucksachen.assert_not_called()
    assert summary.num_documents == 1


def test_run_fetch_asks_for_confirmation_above_cap(settings, query_agent, dip_client, vectorstore):
    settings.dip_max_results_before_confirm = 0
    confirm_calls = []

    def confirm(message: str) -> bool:
        confirm_calls.append(message)
        return True

    run_fetch(
        "Drucksachen der 21. Wahlperiode.",
        settings,
        query_agent=query_agent,
        dip_client=dip_client,
        vectorstore=vectorstore,
        ask_user=lambda q: "",
        confirm=confirm,
    )

    assert len(confirm_calls) == 1


def test_run_fetch_aborts_when_user_declines_confirmation(settings, query_agent, dip_client, vectorstore):
    settings.dip_max_results_before_confirm = 0

    with pytest.raises(FetchAborted):
        run_fetch(
            "Drucksachen der 21. Wahlperiode.",
            settings,
            query_agent=query_agent,
            dip_client=dip_client,
            vectorstore=vectorstore,
            ask_user=lambda q: "",
            confirm=lambda message: False,
        )

    dip_client.download_pdf.assert_not_called()
    vectorstore.add_documents.assert_not_called()
