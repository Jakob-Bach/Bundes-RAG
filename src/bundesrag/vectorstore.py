from collections.abc import Sequence

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_mistralai import MistralAIEmbeddings

from bundesrag.config import Settings

COLLECTION_NAME = "bundesrag"


def get_vectorstore(settings: Settings) -> Chroma:
    embeddings = MistralAIEmbeddings(model=settings.embedding_model, api_key=settings.mistral_api_key)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(settings.chroma_dir),
    )


def add_documents(vectorstore: Chroma, documents: Sequence[Document]) -> None:
    # Deterministic ids (set by the PDF loader) let re-running fetch on
    # overlapping document sets upsert instead of duplicating chunks.
    if not documents:
        return
    ids = [doc.metadata["id"] for doc in documents]
    vectorstore.add_documents(list(documents), ids=ids)
