from langchain_chroma import Chroma

from bundesrag.vectorstore import add_documents, collection_chunk_count, get_vectorstore


def test_get_vectorstore_returns_chroma_instance(settings):
    vectorstore = get_vectorstore(settings)
    assert isinstance(vectorstore, Chroma)


def test_get_vectorstore_without_embeddings_skips_embedding_function(settings):
    vectorstore = get_vectorstore(settings, with_embeddings=False)

    assert isinstance(vectorstore, Chroma)
    assert vectorstore.embeddings is None


def test_collection_chunk_count_reads_collection_count(mocker):
    vectorstore = mocker.Mock()
    vectorstore._collection.count.return_value = 5

    assert collection_chunk_count(vectorstore) == 5


def test_add_documents_does_nothing_for_empty_list(settings, mocker):
    vectorstore = mocker.Mock()
    add_documents(vectorstore, [])
    vectorstore.add_documents.assert_not_called()


def test_add_documents_passes_metadata_ids(mocker):
    vectorstore = mocker.Mock()
    doc = mocker.Mock()
    doc.metadata = {"id": "19/1-p1-0"}

    add_documents(vectorstore, [doc])

    vectorstore.add_documents.assert_called_once_with([doc], ids=["19/1-p1-0"])
