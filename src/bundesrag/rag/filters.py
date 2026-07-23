"""Document-level metadata filters for the ask pipeline (web UI only).

Chunks in the vector store only carry part of the document metadata (no
wahlperiode, no endpoint kind), and Chroma's range operators are
numeric-only, so `datum` (an ISO string) can't be range-filtered natively
either. Instead, the filters are resolved against the indexed-docs manifest
(wahlperiode parsed from the dokumentnummer, kind from the endpoint
subdirectory of the PDF path, date from the recorded datum) and the matching
documents' PDF paths become a `pdf_path $in` where-filter for the similarity
search. This works for already-indexed documents without re-indexing;
documents missing from the manifest (indexed by an old version and no
`status` run since to backfill it) are excluded while a filter is active.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from bundesrag.config import Settings
from bundesrag.ingestion.manifest import DocumentInfo, load_indexed_info
from bundesrag.ingestion.pipeline import document_kind


@dataclass
class AskFilters:
    """Restricts which indexed documents ask retrieval may draw from.

    All fields optional; `kind` is the DIP endpoint the document came from
    ("drucksache" / "plenarprotokoll").
    """

    wahlperiode: int | None = None
    datum_start: date | None = None
    datum_end: date | None = None
    kind: str | None = None

    @property
    def is_active(self) -> bool:
        return any(
            value is not None
            for value in (self.wahlperiode, self.datum_start, self.datum_end, self.kind)
        )


def _wahlperiode_from_dokumentnummer(dokumentnummer: str | None) -> int | None:
    # Dokumentnummern are "<wahlperiode>/<number>", e.g. "21/5".
    if not dokumentnummer:
        return None
    prefix = dokumentnummer.split("/", 1)[0]
    return int(prefix) if prefix.isdigit() else None


def _parse_datum(datum: str | None) -> date | None:
    if not datum:
        return None
    try:
        return date.fromisoformat(datum)
    except ValueError:
        return None


def _matches(filters: AskFilters, pdf_path: Path, info: DocumentInfo, pdf_dir: Path) -> bool:
    # Documents whose relevant metadata is missing/unparseable can't be shown
    # to satisfy an active filter and are excluded rather than guessed at.
    if filters.kind is not None:
        try:
            kind = document_kind(pdf_path, pdf_dir)
        except ValueError:  # manifest path outside the configured pdf_dir
            return False
        if kind != filters.kind:
            return False
    if filters.wahlperiode is not None:
        if _wahlperiode_from_dokumentnummer(info.dokumentnummer) != filters.wahlperiode:
            return False
    if filters.datum_start is not None or filters.datum_end is not None:
        datum = _parse_datum(info.datum)
        if datum is None:
            return False
        if filters.datum_start is not None and datum < filters.datum_start:
            return False
        if filters.datum_end is not None and datum > filters.datum_end:
            return False
    return True


def matching_pdf_paths(filters: AskFilters, settings: Settings) -> list[str]:
    """PDF paths of the indexed documents matching `filters`.

    Returned as strings in the same format the chunk metadata stores
    (`str(pdf_path)`), ready for a `{"pdf_path": {"$in": ...}}` where-filter.
    """
    return [
        str(pdf_path)
        for pdf_path, info in load_indexed_info(settings).items()
        if _matches(filters, pdf_path, info, settings.pdf_dir)
    ]
