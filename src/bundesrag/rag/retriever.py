from langchain_chroma import Chroma
from langchain_core.documents import Document


def retrieve(question: str, vectorstore: Chroma, top_k: int) -> list[Document]:
    return vectorstore.similarity_search(question, k=top_k)
