from langchain_core.documents import Document

from bundesrag.rag.answer_agent import answer_question, citation_for, format_context


def _doc(text: str, label: str, page: int, dokumentnummer: str) -> Document:
    return Document(
        page_content=text,
        metadata={
            "citation_label": label,
            "page": page,
            "dokumentnummer": dokumentnummer,
            "source_url": f"https://example.org/{dokumentnummer}.pdf",
        },
    )


def test_format_context_numbers_chunks_with_citation_labels():
    docs = [
        _doc("Erster Auszug.", "Antrag 19/1", 1, "19/1"),
        _doc("Zweiter Auszug.", "Antrag 19/2", 3, "19/2"),
    ]

    context = format_context(docs)

    assert "[1] Antrag 19/1, Seite 1" in context
    assert "Erster Auszug." in context
    assert "[2] Antrag 19/2, Seite 3" in context


def test_citation_for_includes_label_page_and_dokumentnummer():
    doc = _doc("Text", "Antrag 19/1", 4, "19/1")
    assert citation_for(doc) == "Antrag 19/1, S. 4, Drucksache/Protokoll 19/1"


def test_citation_for_appends_similarity_score():
    doc = _doc("Text", "Antrag 19/1", 4, "19/1")
    assert citation_for(doc, 0.8234) == (
        "Antrag 19/1, S. 4, Drucksache/Protokoll 19/1 (Ähnlichkeit: 0.82)"
    )


def test_answer_question_numbers_sources_like_context(settings, mocker):
    docs = [
        _doc("Erster.", "Antrag 19/1", 1, "19/1"),
        _doc("Zweiter.", "Antrag 19/1", 1, "19/1"),
    ]
    vectorstore = mocker.Mock()
    vectorstore.similarity_search_with_score.return_value = [
        (docs[0], 0.1),
        (docs[1], 0.3),
    ]

    llm = mocker.Mock()
    llm.invoke.return_value = mocker.Mock(content="Die Antwort lautet ... [2]")

    result = answer_question("Worum geht es?", settings, llm=llm, vectorstore=vectorstore)

    assert result.answer_text == "Die Antwort lautet ... [2]"
    # One source per retrieved chunk, numbered like the context block — even
    # for chunks sharing the same citation — so [2] resolves to its chunk.
    assert [source.index for source in result.sources] == [1, 2]
    assert result.sources[0].citation == (
        "Antrag 19/1, S. 1, Drucksache/Protokoll 19/1 (Ähnlichkeit: 0.90)"
    )
    assert result.sources[1].text == "Zweiter."
    assert result.sources[1].page == 1
    assert result.sources[1].source_url == "https://example.org/19/1.pdf"
    messages = llm.invoke.call_args[0][0]
    assert messages[0]["role"] == "system"
    assert "Worum geht es?" in messages[1]["content"]
