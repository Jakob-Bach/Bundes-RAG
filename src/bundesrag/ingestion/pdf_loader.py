from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from bundesrag.dip.models import DocumentMeta


def citation_label(meta: DocumentMeta) -> str:
    # Drucksache.titel is usually populated by the API, but fall back to a
    # type/number/date label for the rare cases where it's missing.
    if meta.titel:
        return meta.titel
    label = (
        f"{meta.drucksachetyp} {meta.dokumentnummer}" if meta.drucksachetyp else meta.dokumentnummer
    )
    return f"{label} ({meta.datum.isoformat()})"


def load_pdf_as_chunks(
    pdf_path: Path,
    meta: DocumentMeta,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[Document]:
    reader = PdfReader(pdf_path)
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    label = citation_label(meta)

    documents = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if not text.strip():
            continue
        for chunk_index, chunk_text in enumerate(splitter.split_text(text)):
            documents.append(
                Document(
                    page_content=chunk_text,
                    metadata={
                        "id": f"{meta.dokumentnummer}-p{page_number}-{chunk_index}",
                        "doc_id": meta.id,
                        "dokumentnummer": meta.dokumentnummer,
                        "citation_label": label,
                        "datum": meta.datum.isoformat(),
                        "page": page_number,
                        "pdf_path": str(pdf_path),
                        "source_url": meta.pdf_url,
                    },
                )
            )
    return documents
