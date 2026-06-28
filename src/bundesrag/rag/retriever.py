from langchain_chroma import Chroma
from langchain_core.documents import Document


def retrieve(question: str, vectorstore: Chroma, top_k: int) -> list[tuple[Document, float]]:
    results = vectorstore.similarity_search_with_score(question, k=top_k)
    # With cosine distance, Chroma returns 1 - cosine_similarity; invert back to similarity.
    return [(doc, 1 - distance) for doc, distance in results]
