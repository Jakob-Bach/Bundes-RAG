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
class Source:
    """One retrieved chunk, numbered to match the [n] citations in the answer.

    `index` is the chunk's number in the context block sent to the LLM, so a
    [n] in the answer text refers to the source with `index == n`. `text` is
    the retrieved chunk text itself (shown in the web UI so users can verify
    the answer against it); `page`/`source_url` allow deep-linking into the
    source PDF (`source_url#page=N`).
    """

    index: int
    citation: str
    text: str
    page: int | None
    source_url: str | None


@dataclass
class AnswerResult:
    answer_text: str
    sources: list[Source]


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

    # One source per retrieved chunk, numbered like the context block above —
    # no deduplication, since a [n] citation in the answer must resolve to
    # exactly the chunk the LLM saw as [n].
    sources = [
        Source(
            index=i,
            citation=citation_for(doc, score),
            text=doc.page_content,
            page=doc.metadata.get("page"),
            source_url=doc.metadata.get("source_url"),
        )
        for i, (doc, score) in enumerate(results, start=1)
    ]

    return AnswerResult(answer_text=answer_text, sources=sources)


def create_chat_llm(settings: Settings) -> ChatLlm:
    from langchain_mistralai import ChatMistralAI

    return ChatMistralAI(model=settings.chat_model, api_key=settings.mistral_api_key)
