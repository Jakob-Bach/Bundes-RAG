from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from langchain_chroma import Chroma
from langchain_core.documents import Document

from bundesrag.config import Settings
from bundesrag.i18n import t
from bundesrag.locales import LANGUAGE_NAMES
from bundesrag.progress import step
from bundesrag.rag.retriever import retrieve

SYSTEM_PROMPT_TEMPLATE = """\
Du beantwortest Fragen zu deutschen Bundestagsdokumenten ausschließlich auf \
Basis der bereitgestellten Textauszüge. Zitiere relevante Aussagen mit der \
Nummer des jeweiligen Auszugs in eckigen Klammern, z. B. [2]. Wenn die \
Auszüge die Frage nicht beantworten können, sage das ausdrücklich, anstatt \
zu raten. Antworte in {language}.
"""


def build_system_prompt(language: str = "de") -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(language=LANGUAGE_NAMES[language])


class ChatLlm(Protocol):
    def invoke(self, messages: list[dict]): ...


@dataclass
class AnswerResult:
    answer_text: str
    sources: list[str]


def format_context(docs: Sequence[Document]) -> str:
    parts = []
    for i, doc in enumerate(docs, start=1):
        label = doc.metadata.get("citation_label", t("unknown_document"))
        page = doc.metadata.get("page")
        header = f"[{i}] {label}" + (t("page_suffix", page=page) if page else "")
        parts.append(f"{header}\n{doc.page_content}")
    return "\n\n".join(parts)


def citation_for(doc: Document, score: float | None = None) -> str:
    label = doc.metadata.get("citation_label", t("unknown_document"))
    page = doc.metadata.get("page")
    dokumentnummer = doc.metadata.get("dokumentnummer")
    parts = [label]
    if page:
        parts.append(t("page_short", page=page))
    if dokumentnummer:
        parts.append(t("document_reference", dokumentnummer=dokumentnummer))
    citation = ", ".join(parts)
    if score is not None:
        citation += t("similarity_suffix", score=f"{score:.2f}")
    return citation


def answer_question(
    question: str, settings: Settings, *, llm: ChatLlm, vectorstore: Chroma
) -> AnswerResult:
    step(1, 2, t("step_search_passages"))
    results = retrieve(question, vectorstore, settings.retrieval_top_k)
    docs = [doc for doc, _ in results]

    step(2, 2, t("step_generate_answer"))
    context = format_context(docs)
    messages = [
        {"role": "system", "content": build_system_prompt(settings.language)},
        {"role": "user", "content": f"Kontext:\n{context}\n\nFrage: {question}"},
    ]
    response = llm.invoke(messages)
    answer_text = getattr(response, "content", response)

    seen: set[str] = set()
    sources = []
    for doc, score in results:
        key = citation_for(doc)
        if key not in seen:
            seen.add(key)
            sources.append(citation_for(doc, score))

    return AnswerResult(answer_text=answer_text, sources=sources)


def create_chat_llm(settings: Settings) -> ChatLlm:
    from langchain_mistralai import ChatMistralAI

    return ChatMistralAI(model=settings.chat_model, api_key=settings.mistral_api_key)
