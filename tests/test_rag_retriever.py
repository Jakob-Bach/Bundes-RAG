from bundesrag.rag.retriever import retrieve


def test_retrieve_delegates_to_similarity_search_with_score(mocker):
    vectorstore = mocker.Mock()
    vectorstore.similarity_search_with_score.return_value = [
        ("doc1", 0.1),
        ("doc2", 0.4),
    ]

    result = retrieve("Wann wurde der EU AI Act debattiert?", vectorstore, top_k=3)

    assert result == [("doc1", 0.9), ("doc2", 0.6)]
    vectorstore.similarity_search_with_score.assert_called_once_with(
        "Wann wurde der EU AI Act debattiert?", k=3
    )
