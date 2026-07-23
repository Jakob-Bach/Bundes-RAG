from datetime import date

from bundesrag.ingestion.manifest import DocumentInfo, save_indexed_info
from bundesrag.rag.filters import AskFilters, matching_pdf_paths


def _info(dokumentnummer: str | None, datum: str | None) -> DocumentInfo:
    return DocumentInfo(
        doc_id="id",
        dokumentnummer=dokumentnummer,
        citation_label="Titel",
        datum=datum,
        source_url=None,
        num_chunks=2,
        num_pages=1,
    )


def _save_corpus(settings):
    drucksache = settings.pdf_dir / "drucksache" / "21_5.pdf"
    protokoll = settings.pdf_dir / "plenarprotokoll" / "20_10.pdf"
    save_indexed_info(
        settings,
        {
            drucksache: _info("21/5", "2025-03-14"),
            protokoll: _info("20/10", "2023-01-02"),
        },
    )
    return drucksache, protokoll


def test_is_active_only_with_a_filter_set():
    assert not AskFilters().is_active
    assert AskFilters(wahlperiode=21).is_active
    assert AskFilters(datum_start=date(2025, 1, 1)).is_active
    assert AskFilters(kind="drucksache").is_active


def test_matching_pdf_paths_by_kind(settings):
    drucksache, _ = _save_corpus(settings)

    paths = matching_pdf_paths(AskFilters(kind="drucksache"), settings)

    assert paths == [str(drucksache)]


def test_matching_pdf_paths_by_wahlperiode(settings):
    _, protokoll = _save_corpus(settings)

    paths = matching_pdf_paths(AskFilters(wahlperiode=20), settings)

    assert paths == [str(protokoll)]


def test_matching_pdf_paths_by_date_range_inclusive(settings):
    drucksache, _ = _save_corpus(settings)

    paths = matching_pdf_paths(
        AskFilters(datum_start=date(2025, 3, 14), datum_end=date(2025, 3, 14)), settings
    )

    assert paths == [str(drucksache)]


def test_matching_pdf_paths_combines_filters(settings):
    _save_corpus(settings)

    paths = matching_pdf_paths(AskFilters(kind="drucksache", wahlperiode=20), settings)

    assert paths == []


def test_document_without_datum_excluded_from_date_filter(settings):
    save_indexed_info(settings, {settings.pdf_dir / "drucksache" / "21_5.pdf": _info("21/5", None)})

    paths = matching_pdf_paths(AskFilters(datum_start=date(2020, 1, 1)), settings)

    assert paths == []


def test_document_with_unparseable_dokumentnummer_excluded_from_wahlperiode_filter(settings):
    save_indexed_info(
        settings, {settings.pdf_dir / "drucksache" / "x.pdf": _info("unbekannt", "2025-01-01")}
    )

    paths = matching_pdf_paths(AskFilters(wahlperiode=21), settings)

    assert paths == []
