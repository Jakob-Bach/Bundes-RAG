from langchain_chroma import Chroma
from langchain_core.documents import Document


def retrieve(
    question: str, vectorstore: Chroma, top_k: int, where: dict | None = None
) -> list[tuple[Document, float]]:
    # `where` is a Chroma metadata filter (e.g. {"pdf_path": {"$in": [...]}});
    # only passed through when set, so unfiltered retrieval stays unchanged.
    kwargs = {"filter": where} if where is not None else {}
    results = vectorstore.similarity_search_with_score(question, k=top_k, **kwargs)
    # With cosine distance, Chroma returns 1 - cosine_similarity; invert back to similarity.
    return [(doc, 1 - distance) for doc, distance in results]
