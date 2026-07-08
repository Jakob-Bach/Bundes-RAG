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
from bundesrag.ingestion.pdf_loader import load_pdf_as_chunks
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
class FileStatus:
    pdf_path: Path
    indexed: bool


@dataclass
class StatusSummary:
    num_downloaded: int
    num_indexed: int
    files: list[FileStatus]


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
    pending = load_pending(settings)
    if on_counts is not None:
        # A downloaded PDF counts as indexed unless it is still pending, the
        # same rule run_status uses.
        pending_paths = {entry.pdf_path for entry in pending}
        pdf_paths = settings.pdf_dir.rglob("*.pdf") if settings.pdf_dir.exists() else []
        num_indexed = sum(1 for path in pdf_paths if path not in pending_paths)
        on_counts(IndexCounts(num_to_index=len(pending), num_indexed=num_indexed))
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


def run_status(settings: Settings) -> StatusSummary:
    pending_paths = {entry.pdf_path for entry in load_pending(settings)}
    pdf_paths = sorted(settings.pdf_dir.rglob("*.pdf")) if settings.pdf_dir.exists() else []
    files = [FileStatus(pdf_path=path, indexed=path not in pending_paths) for path in pdf_paths]
    num_indexed = sum(1 for file in files if file.indexed)
    return StatusSummary(num_downloaded=len(files), num_indexed=num_indexed, files=files)


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
