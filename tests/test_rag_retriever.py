from bundesrag.rag.retriever import retrieve


def test_retrieve_delegates_to_similarity_search(mocker):
    vectorstore = mocker.Mock()
    vectorstore.similarity_search.return_value = ["doc1", "doc2"]

    result = retrieve("Wann wurde der EU AI Act debattiert?", vectorstore, top_k=3)

    assert result == ["doc1", "doc2"]
    vectorstore.similarity_search.assert_called_once_with(
        "Wann wurde der EU AI Act debattiert?", k=3
    )
