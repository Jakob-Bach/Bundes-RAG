from datetime import date

from bundesrag.dip.models import DrucksacheMeta, Fundstelle
from bundesrag.ingestion import pdf_loader
from bundesrag.ingestion.pdf_loader import citation_label, load_pdf_as_chunks


def _meta(titel: str | None) -> DrucksacheMeta:
    return DrucksacheMeta(
        id="68852",
        dokumentnummer="19/1",
        datum=date(2017, 10, 24),
        wahlperiode=19,
        drucksachetyp="Antrag",
        titel=titel,
        fundstelle=Fundstelle(
            id="68852", dokumentart="Drucksache", pdf_url="https://example.org/19_1.pdf"
        ),
    )


def test_citation_label_uses_titel_when_present():
    assert citation_label(_meta("Weitergeltung von Geschäftsordnungsrecht")) == (
        "Weitergeltung von Geschäftsordnungsrecht"
    )


def test_citation_label_falls_back_when_titel_missing():
    assert citation_label(_meta(None)) == "Antrag 19/1 (2017-10-24)"


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakeReader:
    def __init__(self, pages: list[str]) -> None:
        self.pages = [_FakePage(text) for text in pages]


def test_load_pdf_as_chunks_builds_citation_metadata(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pdf_loader,
        "PdfReader",
        lambda path: _FakeReader(["Erste Seite. " * 50, "Zweite Seite."]),
    )
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    docs = load_pdf_as_chunks(pdf_path, _meta("Ein Titel"), chunk_size=200, chunk_overlap=20)

    assert len(docs) >= 2
    first = docs[0]
    assert first.metadata["page"] == 1
    assert first.metadata["citation_label"] == "Ein Titel"
    assert first.metadata["dokumentnummer"] == "19/1"
    assert first.metadata["source_url"] == "https://example.org/19_1.pdf"
    assert first.metadata["id"] == "19/1-p1-0"
    pages_seen = {doc.metadata["page"] for doc in docs}
    assert pages_seen == {1, 2}


def test_load_pdf_as_chunks_skips_blank_pages(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf_loader, "PdfReader", lambda path: _FakeReader(["Inhalt.", "   "]))
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    docs = load_pdf_as_chunks(pdf_path, _meta("Ein Titel"))

    assert {doc.metadata["page"] for doc in docs} == {1}
