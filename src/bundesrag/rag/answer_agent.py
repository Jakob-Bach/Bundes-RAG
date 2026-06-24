from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from langchain_chroma import Chroma
from langchain_core.documents import Document

from bundesrag.config import Settings
from bundesrag.progress import step
from bundesrag.rag.retriever import retrieve

SYSTEM_PROMPT = """\
Du beantwortest Fragen zu deutschen Bundestagsdokumenten ausschließlich auf \
Basis der bereitgestellten Textauszüge. Zitiere relevante Aussagen mit der \
Nummer des jeweiligen Auszugs in eckigen Klammern, z. B. [2]. Wenn die \
Auszüge die Frage nicht beantworten können, sage das ausdrücklich, anstatt \
zu raten. Antworte auf Deutsch.
"""


class ChatLlm(Protocol):
    def invoke(self, messages: list[dict]): ...


@dataclass
class AnswerResult:
    answer_text: str
    sources: list[str]


def format_context(docs: Sequence[Document]) -> str:
    parts = []
    for i, doc in enumerate(docs, start=1):
        label = doc.metadata.get("citation_label", "Unbekanntes Dokument")
        page = doc.metadata.get("page")
        header = f"[{i}] {label}" + (f", Seite {page}" if page else "")
        parts.append(f"{header}\n{doc.page_content}")
    return "\n\n".join(parts)


def citation_for(doc: Document) -> str:
    label = doc.metadata.get("citation_label", "Unbekanntes Dokument")
    page = doc.metadata.get("page")
    dokumentnummer = doc.metadata.get("dokumentnummer")
    parts = [label]
    if page:
        parts.append(f"S. {page}")
    if dokumentnummer:
        parts.append(f"Drucksache/Protokoll {dokumentnummer}")
    return ", ".join(parts)


def answer_question(
    question: str, settings: Settings, *, llm: ChatLlm, vectorstore: Chroma
) -> AnswerResult:
    step(1, 2, "Passagen suchen")
    docs = retrieve(question, vectorstore, settings.retrieval_top_k)

    step(2, 2, "Antwort erzeugen")
    context = format_context(docs)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Kontext:\n{context}\n\nFrage: {question}"},
    ]
    response = llm.invoke(messages)
    answer_text = getattr(response, "content", response)

    seen: set[str] = set()
    sources = []
    for doc in docs:
        citation = citation_for(doc)
        if citation not in seen:
            seen.add(citation)
            sources.append(citation)

    return AnswerResult(answer_text=answer_text, sources=sources)


def create_chat_llm(settings: Settings) -> ChatLlm:
    from langchain_mistralai import ChatMistralAI

    return ChatMistralAI(model=settings.chat_model, api_key=settings.mistral_api_key)
