from collections.abc import Callable
from dataclasses import dataclass

from langchain_chroma import Chroma
from tqdm import tqdm

from bundesrag.config import Settings
from bundesrag.dip.client import DipClient
from bundesrag.dip.models import DrucksacheMeta, PlenarprotokollMeta
from bundesrag.ingestion.pdf_loader import load_pdf_as_chunks
from bundesrag.progress import step
from bundesrag.query_agent.agent import QueryAgent
from bundesrag.query_agent.schema import DipQueryFilters
from bundesrag.vectorstore import add_documents

DocumentMeta = DrucksacheMeta | PlenarprotokollMeta


@dataclass
class FetchSummary:
    num_documents: int
    num_chunks: int


class FetchAborted(RuntimeError):
    pass


def _default_confirm(message: str) -> bool:
    return input(message).strip().lower() in ("j", "ja", "y", "yes")


def run_fetch(
    nl_prompt: str,
    settings: Settings,
    *,
    query_agent: QueryAgent,
    dip_client: DipClient,
    vectorstore: Chroma,
    ask_user: Callable[[str], str] = input,
    confirm: Callable[[str], bool] = _default_confirm,
) -> FetchSummary:
    step(1, 4, "Anfrage interpretieren")
    filters = query_agent.build_query(nl_prompt, ask_user=ask_user)

    step(2, 4, "Dokumente suchen")
    metas = _list_documents(dip_client, filters)
    if len(metas) > settings.dip_max_results_before_confirm:
        proceed = confirm(
            f"{len(metas)} Dokumente gefunden, mehr als der Grenzwert von "
            f"{settings.dip_max_results_before_confirm}. Trotzdem alle herunterladen? [j/N] "
        )
        if not proceed:
            raise FetchAborted(f"Abgebrochen: {len(metas)} Dokumente überschreiten den Grenzwert.")

    step(3, 4, "PDFs herunterladen")
    pdf_paths = {}
    for meta in tqdm(metas, desc="Download"):
        pdf_url = meta.fundstelle.pdf_url
        if not pdf_url:
            continue
        dest = settings.pdf_dir / filters.endpoint / f"{meta.dokumentnummer.replace('/', '_')}.pdf"
        pdf_paths[meta.id] = dip_client.download_pdf(pdf_url, dest)

    step(4, 4, "Indexieren")
    all_chunks = []
    for meta in tqdm(metas, desc="Indexieren"):
        pdf_path = pdf_paths.get(meta.id)
        if pdf_path is None:
            continue
        all_chunks.extend(
            load_pdf_as_chunks(pdf_path, meta, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
        )
    add_documents(vectorstore, all_chunks)

    return FetchSummary(num_documents=len(pdf_paths), num_chunks=len(all_chunks))


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
