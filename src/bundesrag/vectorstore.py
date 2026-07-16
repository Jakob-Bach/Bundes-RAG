from collections.abc import Sequence

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_mistralai import MistralAIEmbeddings

from bundesrag.config import Settings

COLLECTION_NAME = "bundesrag"


def get_vectorstore(settings: Settings, *, with_embeddings: bool = True) -> Chroma:
    """Construct the Chroma vector store.

    `with_embeddings=False` skips constructing the Mistral embeddings client,
    whose constructor tries to download a tokenizer from Hugging Face — a
    gated repo, so without an HF_TOKEN the request fails and a dummy
    tokenizer is used (only batch sizing is affected). The failure is
    usually fast but blocks on the network and can take up to ~10s (HF
    throttling/timeout). Callers that only run metadata operations
    (count/get/delete — i.e. status, clear, single-file delete) never embed
    anything and don't need it.
    """
    embeddings = None
    if with_embeddings:
        embeddings = MistralAIEmbeddings(
            model=settings.embedding_model, api_key=settings.mistral_api_key
        )
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(settings.chroma_dir),
        collection_metadata={"hnsw:space": "cosine"},
    )


def collection_chunk_count(vectorstore: Chroma) -> int:
    # A plain SQL COUNT on the collection — unlike get(), it doesn't fetch or
    # deserialize any records.
    return vectorstore._collection.count()


def add_documents(vectorstore: Chroma, documents: Sequence[Document]) -> None:
    # Deterministic ids (set by the PDF loader) let re-running fetch on
    # overlapping document sets upsert instead of duplicating chunks.
    if not documents:
        return
    ids = [doc.metadata["id"] for doc in documents]
    vectorstore.add_documents(list(documents), ids=ids)
