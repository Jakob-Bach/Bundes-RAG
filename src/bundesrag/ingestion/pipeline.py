from collections.abc import Callable
from dataclasses import dataclass

from langchain_chroma import Chroma
from tqdm import tqdm

from bundesrag.config import Settings
from bundesrag.dip.client import DipClient
from bundesrag.dip.models import DrucksacheMeta, PlenarprotokollMeta
from bundesrag.ingestion.manifest import PendingDocument, add_pending, load_pending, remove_pending
from bundesrag.ingestion.pdf_loader import load_pdf_as_chunks
from bundesrag.progress import step
from bundesrag.query_agent.agent import QueryAgent
from bundesrag.query_agent.schema import DipQueryFilters
from bundesrag.vectorstore import add_documents

DocumentMeta = DrucksacheMeta | PlenarprotokollMeta


@dataclass
class DownloadSummary:
    num_documents: int


@dataclass
class IndexSummary:
    num_documents: int
    num_chunks: int


class DownloadAborted(RuntimeError):
    pass


def _default_confirm(message: str) -> bool:
    return input(message).strip().lower() in ("j", "ja", "y", "yes")


def run_download(
    nl_prompt: str,
    settings: Settings,
    *,
    query_agent: QueryAgent,
    dip_client: DipClient,
    ask_user: Callable[[str], str] = input,
    confirm: Callable[[str], bool] = _default_confirm,
) -> DownloadSummary:
    step(1, 3, "Anfrage interpretieren")
    filters = query_agent.build_query(nl_prompt, ask_user=ask_user)

    step(2, 3, "Dokumente suchen")
    metas = _list_documents(dip_client, filters)
    if len(metas) > settings.dip_max_results_before_confirm:
        proceed = confirm(
            f"{len(metas)} Dokumente gefunden, mehr als der Grenzwert von "
            f"{settings.dip_max_results_before_confirm}. Trotzdem alle herunterladen? [j/N] "
        )
        if not proceed:
            raise DownloadAborted(f"Abgebrochen: {len(metas)} Dokumente überschreiten den Grenzwert.")

    step(3, 3, "PDFs herunterladen")
    pending = []
    for meta in tqdm(metas, desc="Download"):
        pdf_url = meta.fundstelle.pdf_url
        if not pdf_url:
            continue
        dest = settings.pdf_dir / filters.endpoint / f"{meta.dokumentnummer.replace('/', '_')}.pdf"
        pdf_path = dip_client.download_pdf(pdf_url, dest)
        pending.append(
            PendingDocument(kind=filters.endpoint, pdf_path=pdf_path, meta=meta.model_dump(mode="json"))
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
            entry.pdf_path, meta, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )
        add_documents(vectorstore, chunks)
        num_documents += 1
        num_chunks += len(chunks)
        # Remove right after each document so a crash/abort mid-run leaves only the
        # not-yet-indexed documents pending, not the whole batch.
        remove_pending(settings, entry.pdf_path)

    return IndexSummary(num_documents=num_documents, num_chunks=num_chunks)


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
                urheber=filters.urheber or None,
                ressort_fdf=filters.ressort_fdf or None,
                titel=filters.titel or None,
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
