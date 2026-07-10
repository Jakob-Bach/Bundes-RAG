import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
from langchain_chroma import Chroma
from tqdm import tqdm

from bundesrag.config import Settings
from bundesrag.dip.client import DipClient
from bundesrag.dip.models import DocumentMeta
from bundesrag.i18n import t
from bundesrag.ingestion.manifest import (
    PendingDocument,
    add_pending,
    load_pending,
    remove_pending,
    save_pending,
)
from bundesrag.ingestion.pdf_loader import citation_label, load_pdf_as_chunks, pdf_page_count
from bundesrag.progress import step
from bundesrag.query_agent.agent import QueryAgent
from bundesrag.query_agent.schema import DipQueryFilters
from bundesrag.vectorstore import add_documents

logger = logging.getLogger(__name__)


@dataclass
class DownloadCounts:
    """Quantities shown in the download count confirmation dialogue."""

    num_matched: int
    num_existing: int
    num_to_download: int


@dataclass
class DownloadSummary:
    num_documents: int
    num_failed: int = 0
    num_skipped: int = 0


@dataclass
class IndexCounts:
    """Quantities shown when indexing starts."""

    num_to_index: int
    num_indexed: int


@dataclass
class IndexSummary:
    num_documents: int
    num_chunks: int


@dataclass
class DeleteSummary:
    num_files: int


@dataclass
class DocumentInfo:
    """Per-document metadata shown in the status output.

    For indexed documents this is aggregated from the chunk metadata in the
    vector store (all chunks of a document share the document-level fields;
    `page` and the chunk id vary per chunk and are aggregated into counts).
    For not-yet-indexed documents it comes from the pending manifest, with
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


@dataclass
class FileStatus:
    pdf_path: Path
    indexed: bool
    # The DIP endpoint the document came from ("drucksache" /
    # "plenarprotokoll"), read back from its subdirectory under pdf_dir.
    kind: str = ""
    info: DocumentInfo | None = None


@dataclass
class StatusSummary:
    num_downloaded: int
    num_indexed: int
    files: list[FileStatus]
    num_chunks: int = 0
    pdf_size_bytes: int = 0
    vectorstore_size_bytes: int = 0


class DownloadAborted(RuntimeError):
    pass


class OperationCancelled(RuntimeError):
    pass


# Reports per-item progress of a long loop as (num_done, total).
ProgressCallback = Callable[[int, int], None]

# Returns True once the user has requested that the running operation stop;
# checked between items, so the current item still finishes first.
CancelCheck = Callable[[], bool]


def _report_progress(on_progress: ProgressCallback | None, num_done: int, total: int) -> None:
    if on_progress is not None:
        on_progress(num_done, total)


def _check_cancelled(should_cancel: CancelCheck | None) -> None:
    if should_cancel is not None and should_cancel():
        raise OperationCancelled(t("operation_cancelled"))


def run_download(
    nl_prompt: str,
    settings: Settings,
    *,
    query_agent: QueryAgent,
    dip_client: DipClient,
    ask_user: Callable[[str], str],
    confirm_count: Callable[[DownloadCounts], int],
    confirm_filters: Callable[[DipQueryFilters], bool],
    on_progress: ProgressCallback | None = None,
    should_cancel: CancelCheck | None = None,
) -> DownloadSummary:
    step(1, 3, t("step_interpret_request"))
    filters = query_agent.build_query(nl_prompt, ask_user=ask_user, confirm_filters=confirm_filters)

    step(2, 3, t("step_search_documents"))
    _check_cancelled(should_cancel)
    metas = _list_documents(dip_client, filters)

    # Skip documents whose PDF already exists locally, so repeating a query
    # neither re-downloads nor re-queues them for indexing. This happens
    # before the count confirmation so the dialogue can report how many of
    # the matches would actually be downloaded; the user's chosen count and
    # the progress bar then only cover actual downloads.
    to_download = []
    num_skipped = 0
    for meta in metas:
        dest = settings.pdf_dir / filters.endpoint / f"{meta.dokumentnummer.replace('/', '_')}.pdf"
        if dest.exists():
            num_skipped += 1
            continue
        to_download.append((meta, dest))

    if to_download:
        counts = DownloadCounts(
            num_matched=len(metas),
            num_existing=num_skipped,
            num_to_download=len(to_download),
        )
        chosen_count = confirm_count(counts)
        if chosen_count <= 0:
            raise DownloadAborted(t("download_aborted", count=len(to_download)))
        if chosen_count < len(to_download):
            to_download = sorted(to_download, key=lambda item: item[0].datum, reverse=True)[
                :chosen_count
            ]

    step(3, 3, t("step_download_pdfs"))
    pending = []
    num_failed = 0
    _report_progress(on_progress, 0, len(to_download))
    # add_pending runs in a finally so that an interrupted loop (Ctrl+C, web
    # cancel) still queues the already-downloaded PDFs for indexing — otherwise
    # later runs would skip them as existing without ever indexing them.
    try:
        for num_done, (meta, dest) in enumerate(tqdm(to_download, desc="Download"), start=1):
            _check_cancelled(should_cancel)
            pdf_url = meta.pdf_url
            if not pdf_url:
                logger.warning("no pdf_url for %s, skipping", meta.dokumentnummer)
                num_failed += 1
            else:
                try:
                    pdf_path = dip_client.download_pdf(pdf_url, dest)
                except httpx.HTTPError:
                    logger.warning(
                        "download failed for %s, skipping", meta.dokumentnummer, exc_info=True
                    )
                    num_failed += 1
                else:
                    pending.append(
                        PendingDocument(
                            kind=filters.endpoint,
                            pdf_path=pdf_path,
                            meta=meta.model_dump(mode="json"),
                        )
                    )
            _report_progress(on_progress, num_done, len(to_download))
    finally:
        add_pending(settings, pending)

    return DownloadSummary(
        num_documents=len(pending), num_failed=num_failed, num_skipped=num_skipped
    )


def run_index(
    settings: Settings,
    *,
    vectorstore: Chroma,
    on_counts: Callable[[IndexCounts], None] | None = None,
    on_progress: ProgressCallback | None = None,
    should_cancel: CancelCheck | None = None,
) -> IndexSummary:
    # The scan prunes pending entries whose PDF was deleted manually, so the
    # loop below only sees files that exist instead of failing on the first
    # missing one; num_indexed is the same count the status output shows.
    pending, status = _scan_documents(settings)
    if on_counts is not None:
        on_counts(IndexCounts(num_to_index=len(pending), num_indexed=status.num_indexed))
    num_documents = 0
    num_chunks = 0
    _report_progress(on_progress, 0, len(pending))
    for entry in tqdm(pending, desc="Indexieren"):
        _check_cancelled(should_cancel)
        meta = entry.resolve_meta()
        chunks = load_pdf_as_chunks(
            entry.pdf_path,
            meta,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        add_documents(vectorstore, chunks)
        num_documents += 1
        num_chunks += len(chunks)
        # Remove right after each document so a crash/abort mid-run leaves only the
        # not-yet-indexed documents pending, not the whole batch.
        remove_pending(settings, entry.pdf_path)
        _report_progress(on_progress, num_documents, len(pending))

    return IndexSummary(num_documents=num_documents, num_chunks=num_chunks)


def run_delete_all(settings: Settings, *, vectorstore: Chroma) -> DeleteSummary:
    num_files = 0
    if settings.pdf_dir.exists():
        for pdf_path in settings.pdf_dir.rglob("*.pdf"):
            pdf_path.unlink()
            num_files += 1

    vectorstore.delete_collection()
    save_pending(settings, [])
    return DeleteSummary(num_files=num_files)


def run_delete_file(pdf_path: Path, settings: Settings, *, vectorstore: Chroma) -> None:
    """Delete a single downloaded PDF, plus its chunks and pending entry.

    `pdf_path` must be one of the files the status scan reports; anything else
    raises FileNotFoundError. Matching against the scanned files instead of
    trusting the caller's path keeps the web endpoint from deleting arbitrary
    files outside `pdf_dir`.
    """
    _, status = _scan_documents(settings)
    match = next((file for file in status.files if file.pdf_path == pdf_path), None)
    if match is None:
        raise FileNotFoundError(str(pdf_path))
    # Chunks are deleted before the file so a vector-store failure leaves a
    # retryable state instead of orphaned chunks whose PDF is gone. The delete
    # runs even for not-indexed files: an index run that crashed between
    # embedding a document and updating the manifest leaves such chunks behind.
    vectorstore.delete(where={"pdf_path": str(match.pdf_path)})
    match.pdf_path.unlink()
    remove_pending(settings, match.pdf_path)


def _document_kind(pdf_path: Path, pdf_dir: Path) -> str:
    # PDFs are stored under pdf_dir/<endpoint>/, so the first path component
    # below pdf_dir is the endpoint the document was downloaded from.
    parts = pdf_path.relative_to(pdf_dir).parts
    return parts[0] if len(parts) > 1 else ""


def _scan_documents(settings: Settings) -> tuple[list[PendingDocument], StatusSummary]:
    """Report the pending entries and the per-file status of all PDFs on disk.

    Pending entries whose PDF no longer exists on disk (deleted manually) are
    dropped from the manifest first: they can never be indexed, and a stale
    entry would otherwise make every `index` run fail on the missing file.
    """
    pending = load_pending(settings)
    existing = [entry for entry in pending if entry.pdf_path.exists()]
    if len(existing) < len(pending):
        logger.info(
            "pruned %d pending entries whose PDFs no longer exist",
            len(pending) - len(existing),
        )
        save_pending(settings, existing)
    pending_paths = {entry.pdf_path for entry in existing}
    pdf_paths = sorted(settings.pdf_dir.rglob("*.pdf")) if settings.pdf_dir.exists() else []
    files = [
        FileStatus(
            pdf_path=path,
            indexed=path not in pending_paths,
            kind=_document_kind(path, settings.pdf_dir),
        )
        for path in pdf_paths
    ]
    num_indexed = sum(1 for file in files if file.indexed)
    summary = StatusSummary(num_downloaded=len(files), num_indexed=num_indexed, files=files)
    return existing, summary


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(entry.stat().st_size for entry in path.rglob("*") if entry.is_file())


# Chunk metadata is fetched from Chroma in batches: an unbounded get() on a
# large collection fails with "too many SQL variables" (one variable per
# fetched record in Chroma's SQLite layer, which allows at most ~32k).
_CHUNK_FETCH_BATCH_SIZE = 5000


def _collect_index_info(vectorstore: Chroma) -> tuple[int, dict[Path, DocumentInfo]]:
    """Fetch all chunk metadata and aggregate it per document (keyed by PDF path)."""
    metadatas: list[dict] = []
    offset = 0
    while True:
        data = vectorstore.get(include=["metadatas"], limit=_CHUNK_FETCH_BATCH_SIZE, offset=offset)
        batch = data.get("metadatas") or []
        metadatas.extend(batch)
        if len(batch) < _CHUNK_FETCH_BATCH_SIZE:
            break
        offset += _CHUNK_FETCH_BATCH_SIZE
    chunks_by_path: dict[Path, list[dict]] = {}
    for metadata in metadatas:
        pdf_path = metadata.get("pdf_path")
        if pdf_path:
            chunks_by_path.setdefault(Path(pdf_path), []).append(metadata)
    info_by_path = {
        path: DocumentInfo(
            doc_id=chunks[0].get("doc_id"),
            dokumentnummer=chunks[0].get("dokumentnummer"),
            citation_label=chunks[0].get("citation_label"),
            datum=chunks[0].get("datum"),
            source_url=chunks[0].get("source_url"),
            num_chunks=len(chunks),
            num_pages=len({chunk.get("page") for chunk in chunks}),
        )
        for path, chunks in chunks_by_path.items()
    }
    return len(metadatas), info_by_path


def _pending_document_info(entry: PendingDocument) -> DocumentInfo:
    meta = entry.resolve_meta()
    return DocumentInfo(
        doc_id=meta.id,
        dokumentnummer=meta.dokumentnummer,
        citation_label=citation_label(meta),
        datum=meta.datum.isoformat(),
        source_url=meta.pdf_url,
        num_chunks=None,
        num_pages=pdf_page_count(entry.pdf_path),
    )


def run_status(settings: Settings, *, vectorstore: Chroma) -> StatusSummary:
    pending, summary = _scan_documents(settings)
    summary.num_chunks, info_by_path = _collect_index_info(vectorstore)
    # Not-yet-indexed documents have no (complete) chunk metadata in the
    # vector store; their info comes from the pending manifest instead, which
    # stores the full DIP record. It overrides any partial chunk data so the
    # info source always matches the file's indexed/not-indexed status.
    for entry in pending:
        info_by_path[entry.pdf_path] = _pending_document_info(entry)
    for file in summary.files:
        file.info = info_by_path.get(file.pdf_path)
    summary.pdf_size_bytes = _dir_size_bytes(settings.pdf_dir)
    summary.vectorstore_size_bytes = _dir_size_bytes(settings.chroma_dir)
    return summary


def _list_documents(dip_client: DipClient, filters: DipQueryFilters) -> list[DocumentMeta]:
    if filters.endpoint == "drucksache":
        return list(
            dip_client.list_drucksachen(
                datum_start=filters.datum_start,
                datum_end=filters.datum_end,
                wahlperiode=filters.wahlperiode,
                dokumentnummer=filters.dokumentnummer,
                drucksachetyp=filters.drucksachetyp,
                zuordnung=filters.zuordnung,
                urheber=filters.urheber,
                ressort_fdf=filters.ressort_fdf,
                titel=filters.titel,
            )
        )
    return list(
        dip_client.list_plenarprotokolle(
            datum_start=filters.datum_start,
            datum_end=filters.datum_end,
            wahlperiode=filters.wahlperiode,
            dokumentnummer=filters.dokumentnummer,
            zuordnung=filters.zuordnung,
        )
    )
