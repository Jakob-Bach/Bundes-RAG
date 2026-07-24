from types import SimpleNamespace

from langchain_core.documents import Document

from bundesrag.ingestion.manifest import DocumentInfo, save_indexed_info
from bundesrag.rag.answer_agent import answer_question, citation_for, format_context
from bundesrag.rag.filters import AskFilters
from bundesrag.usage import load_usage_totals


def _doc(
    text: str, label: str, page: int, dokumentnummer: str, datum: str | None = "2025-03-14"
) -> Document:
    metadata = {
        "citation_label": label,
        "page": page,
        "dokumentnummer": dokumentnummer,
        "source_url": f"https://example.org/{dokumentnummer}.pdf",
    }
    if datum is not None:
        metadata["datum"] = datum
    return Document(page_content=text, metadata=metadata)


def test_format_context_numbers_chunks_with_citation_labels_and_dates():
    docs = [
        _doc("Erster Auszug.", "Antrag 19/1", 1, "19/1"),
        _doc("Zweiter Auszug.", "Antrag 19/2", 3, "19/2", datum="2025-04-01"),
    ]

    context = format_context(docs)

    assert "[1] Antrag 19/1 (2025-03-14), Seite 1" in context
    assert "Erster Auszug." in context
    assert "[2] Antrag 19/2 (2025-04-01), Seite 3" in context


def test_citation_for_includes_label_date_page_and_dokumentnummer():
    doc = _doc("Text", "Antrag 19/1", 4, "19/1")
    assert citation_for(doc) == "Antrag 19/1 (2025-03-14), S. 4, Drucksache/Protokoll 19/1"


def test_citation_for_appends_similarity_score():
    doc = _doc("Text", "Antrag 19/1", 4, "19/1")
    assert citation_for(doc, 0.8234) == (
        "Antrag 19/1 (2025-03-14), S. 4, Drucksache/Protokoll 19/1 (Ähnlichkeit: 0.82)"
    )


def test_citation_for_without_datum_metadata_omits_date():
    # Chunks indexed before `datum` was stored in chunk metadata.
    doc = _doc("Text", "Antrag 19/1", 4, "19/1", datum=None)
    assert citation_for(doc) == "Antrag 19/1, S. 4, Drucksache/Protokoll 19/1"


def test_citation_for_does_not_double_date_already_in_label():
    # Fallback labels (missing titel) already embed the date, see
    # pdf_loader.citation_label.
    doc = _doc("Text", "Antrag 19/1 (2025-03-14)", 4, "19/1")
    assert citation_for(doc) == "Antrag 19/1 (2025-03-14), S. 4, Drucksache/Protokoll 19/1"


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
        "Antrag 19/1 (2025-03-14), S. 1, Drucksache/Protokoll 19/1 (Ähnlichkeit: 0.90)"
    )
    assert result.sources[1].text == "Zweiter."
    assert result.sources[1].page == 1
    assert result.sources[1].source_url == "https://example.org/19/1.pdf"
    messages = llm.invoke.call_args[0][0]
    assert messages[0]["role"] == "system"
    assert "Worum geht es?" in messages[1]["content"]


def test_answer_question_reports_ask_stats(settings, mocker):
    save_indexed_info(
        settings,
        {
            settings.pdf_dir / "drucksache" / "19_1.pdf": _indexed_info("19/1", "2025-03-14"),
            settings.pdf_dir / "drucksache" / "19_2.pdf": _indexed_info("19/2", "2025-04-01"),
        },
    )
    vectorstore = mocker.Mock()
    vectorstore._collection.count.return_value = 42
    vectorstore.similarity_search_with_score.return_value = [
        (_doc("Erster.", "Antrag 19/1", 1, "19/1"), 0.1)
    ]
    llm = mocker.Mock()
    llm.invoke.return_value = mocker.Mock(content="Die Antwort.")

    result = answer_question("Worum geht es?", settings, llm=llm, vectorstore=vectorstore)

    assert result.ask_stats.num_documents == 2
    assert result.ask_stats.num_chunks == 42
    assert result.ask_stats.top_k == settings.retrieval_top_k
    # No filter, so the filtered figures stay unset.
    assert result.ask_stats.num_filtered_documents is None
    assert result.ask_stats.num_filtered_chunks is None


def test_answer_question_reports_filtered_ask_stats(settings, mocker):
    matching = settings.pdf_dir / "drucksache" / "21_5.pdf"
    other = settings.pdf_dir / "plenarprotokoll" / "20_10.pdf"
    save_indexed_info(
        settings,
        {
            matching: _indexed_info("21/5", "2025-03-14"),
            other: _indexed_info("20/10", "2023-01-02"),
        },
    )
    vectorstore = mocker.Mock()
    vectorstore._collection.count.return_value = 4
    vectorstore.similarity_search_with_score.return_value = [
        (_doc("Erster.", "Antrag 21/5", 1, "21/5"), 0.1)
    ]
    llm = mocker.Mock()
    llm.invoke.return_value = mocker.Mock(content="Die Antwort.")

    result = answer_question(
        "Worum geht es?",
        settings,
        llm=llm,
        vectorstore=vectorstore,
        filters=AskFilters(wahlperiode=21),
    )

    assert result.ask_stats.num_documents == 2
    assert result.ask_stats.num_chunks == 4
    # Only the one wahlperiode-21 document matches; each _indexed_info has 2 chunks.
    assert result.ask_stats.num_filtered_documents == 1
    assert result.ask_stats.num_filtered_chunks == 2


def test_answer_question_records_token_usage(settings, mocker):
    vectorstore = mocker.Mock()
    vectorstore.similarity_search_with_score.return_value = [
        (_doc("Erster.", "Antrag 19/1", 1, "19/1"), 0.1)
    ]
    llm = mocker.Mock()
    llm.invoke.return_value = SimpleNamespace(
        content="Die Antwort.", usage_metadata={"input_tokens": 11, "output_tokens": 4}
    )

    result = answer_question("Worum geht es?", settings, llm=llm, vectorstore=vectorstore)

    assert result.usage.chat_calls == 1
    assert result.usage.chat_input_tokens == 11
    assert result.usage.chat_output_tokens == 4
    # The operation is also accumulated into the persisted all-time totals.
    totals = load_usage_totals(settings)
    assert totals["ask"].num_operations == 1
    assert totals["ask"].chat_input_tokens == 11


def _indexed_info(dokumentnummer: str, datum: str) -> DocumentInfo:
    return DocumentInfo(
        doc_id="id",
        dokumentnummer=dokumentnummer,
        citation_label="Titel",
        datum=datum,
        source_url=None,
        num_chunks=2,
        num_pages=1,
    )


def test_answer_question_filters_restrict_retrieval_to_matching_documents(settings, mocker):
    matching = settings.pdf_dir / "drucksache" / "21_5.pdf"
    other = settings.pdf_dir / "plenarprotokoll" / "20_10.pdf"
    save_indexed_info(
        settings,
        {
            matching: _indexed_info("21/5", "2025-03-14"),
            other: _indexed_info("20/10", "2023-01-02"),
        },
    )
    vectorstore = mocker.Mock()
    vectorstore.similarity_search_with_score.return_value = [
        (_doc("Erster.", "Antrag 21/5", 1, "21/5"), 0.1)
    ]
    llm = mocker.Mock()
    llm.invoke.return_value = mocker.Mock(content="Die Antwort.")

    answer_question(
        "Worum geht es?",
        settings,
        llm=llm,
        vectorstore=vectorstore,
        filters=AskFilters(wahlperiode=21),
    )

    vectorstore.similarity_search_with_score.assert_called_once_with(
        "Worum geht es?",
        k=settings.retrieval_top_k,
        filter={"pdf_path": {"$in": [str(matching)]}},
    )


def test_answer_question_without_filter_match_skips_retrieval_and_llm(settings, mocker):
    # No indexed-docs manifest at all, so an active filter matches nothing.
    vectorstore = mocker.Mock()
    llm = mocker.Mock()

    result = answer_question(
        "Worum geht es?",
        settings,
        llm=llm,
        vectorstore=vectorstore,
        filters=AskFilters(kind="drucksache"),
    )

    assert result.answer_text == "Keine indexierten Dokumente entsprechen den gewählten Filtern."
    assert result.sources == []
    vectorstore.similarity_search_with_score.assert_not_called()
    llm.invoke.assert_not_called()
