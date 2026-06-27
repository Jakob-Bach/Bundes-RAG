from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

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


@dataclass
class DownloadSummary:
    num_documents: int


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


def run_download(
    nl_prompt: str,
    settings: Settings,
    *,
    query_agent: QueryAgent,
    dip_client: DipClient,
    ask_user: Callable[[str], str],
    confirm_count: Callable[[int], int],
    confirm_filters: Callable[[DipQueryFilters], bool],
) -> DownloadSummary:
    step(1, 3, t("step_interpret_request"))
    filters = query_agent.build_query(nl_prompt, ask_user=ask_user, confirm_filters=confirm_filters)

    step(2, 3, t("step_search_documents"))
    metas = _list_documents(dip_client, filters)
    if metas:
        chosen_count = confirm_count(len(metas))
        if chosen_count <= 0:
            raise DownloadAborted(t("download_aborted", count=len(metas)))
        if chosen_count < len(metas):
            metas = sorted(metas, key=lambda meta: meta.datum, reverse=True)[:chosen_count]

    step(3, 3, t("step_download_pdfs"))
    pending = []
    for meta in tqdm(metas, desc="Download"):
        pdf_url = meta.pdf_url
        if not pdf_url:
            continue
        dest = settings.pdf_dir / filters.endpoint / f"{meta.dokumentnummer.replace('/', '_')}.pdf"
        pdf_path = dip_client.download_pdf(pdf_url, dest)
        pending.append(
            PendingDocument(
                kind=filters.endpoint,
                pdf_path=pdf_path,
                meta=meta.model_dump(mode="json"),
            )
        )

    add_pending(settings, pending)
    return DownloadSummary(num_documents=len(pending))


def run_index(settings: Settings, *, vectorstore: Chroma) -> IndexSummary:
    pending = load_pending(settings)
    num_documents = 0
    num_chunks = 0
    for entry in tqdm(pending, desc="Indexieren"):
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
