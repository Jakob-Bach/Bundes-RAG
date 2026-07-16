import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from bundesrag.config import Settings
from bundesrag.dip.models import DocumentMeta

logger = logging.getLogger(__name__)


class DocumentInfo(BaseModel):
    """Per-document metadata shown in the status output.

    For indexed documents this is recorded in the indexed-docs manifest when
    `index` finishes a document (or backfilled once from the vector store's
    chunk metadata, for documents indexed before the manifest existed). For
    not-yet-indexed documents it is derived from the pending manifest, with
    the page count read from the PDF itself and `num_chunks` left None —
    chunks only exist after indexing.
    """

    doc_id: str | None
    dokumentnummer: str | None
    citation_label: str | None
    datum: str | None
    source_url: str | None
    num_chunks: int | None
    num_pages: int | None


class PendingDocument(BaseModel):
    """A downloaded PDF that still needs to be chunked/embedded into the vector
    store."""

    kind: Literal["drucksache", "plenarprotokoll"]
    pdf_path: Path
    meta: dict

    def resolve_meta(self) -> DocumentMeta:
        return DocumentMeta.model_validate(self.meta)


def manifest_path(settings: Settings) -> Path:
    return settings.data_dir / "pending_index.json"


def load_pending(settings: Settings) -> list[PendingDocument]:
    path = manifest_path(settings)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [PendingDocument.model_validate(item) for item in raw]


def save_pending(settings: Settings, entries: list[PendingDocument]) -> None:
    path = manifest_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [entry.model_dump(mode="json") for entry in entries],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def add_pending(settings: Settings, new_entries: list[PendingDocument]) -> None:
    if not new_entries:
        return
    # Deduplicate by pdf_path (newest entry wins) so re-downloading the same
    # documents doesn't list them as pending twice and double the index work.
    by_path = {entry.pdf_path: entry for entry in load_pending(settings)}
    for entry in new_entries:
        by_path[entry.pdf_path] = entry
    save_pending(settings, list(by_path.values()))


def remove_pending(settings: Settings, pdf_path: Path) -> None:
    entries = load_pending(settings)
    remaining = [entry for entry in entries if entry.pdf_path != pdf_path]
    save_pending(settings, remaining)


def indexed_info_path(settings: Settings) -> Path:
    return settings.data_dir / "indexed_docs.json"


def load_indexed_info(settings: Settings) -> dict[Path, DocumentInfo]:
    path = indexed_info_path(settings)
    if not path.exists():
        return {}
    # Unlike the pending manifest, this file is derived data: run_status
    # rebuilds missing entries from the vector store's chunk metadata. So an
    # unreadable/corrupt file degrades to that backfill instead of making
    # every status run fail.
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {Path(key): DocumentInfo.model_validate(value) for key, value in raw.items()}
    except Exception:
        logger.warning("could not read indexed-docs manifest %s, rebuilding", path, exc_info=True)
        return {}


def save_indexed_info(settings: Settings, info_by_path: dict[Path, DocumentInfo]) -> None:
    path = indexed_info_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {str(key): info.model_dump(mode="json") for key, info in info_by_path.items()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def add_indexed_info(settings: Settings, pdf_path: Path, info: DocumentInfo) -> None:
    info_by_path = load_indexed_info(settings)
    info_by_path[pdf_path] = info
    save_indexed_info(settings, info_by_path)


def remove_indexed_info(settings: Settings, pdf_path: Path) -> None:
    info_by_path = load_indexed_info(settings)
    if info_by_path.pop(pdf_path, None) is not None:
        save_indexed_info(settings, info_by_path)
