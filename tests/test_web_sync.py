import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from pypdf import PdfWriter

from bundesrag.config import Settings
from bundesrag.i18n import set_language, t
from bundesrag.ingestion.manifest import PendingDocument, add_pending
from bundesrag.web.app import create_app
from bundesrag.web.dependencies import (
    get_chat_llm,
    get_metadata_vectorstore_dep,
    get_vectorstore_dep,
)


@pytest.fixture
def app(settings):
    return create_app(settings=settings)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def vectorstore(app, mocker):
    store = mocker.Mock()
    store.get.return_value = {"ids": [], "metadatas": []}
    store._collection.count.return_value = 0
    app.dependency_overrides[get_vectorstore_dep] = lambda: store
    app.dependency_overrides[get_metadata_vectorstore_dep] = lambda: store
    return store


@pytest.fixture
def chat_llm(app, mocker):
    llm = mocker.Mock()
    llm.invoke.return_value = "Die Antwort."
    app.dependency_overrides[get_chat_llm] = lambda: llm
    return llm


def test_ask_returns_answer_with_sources(client, vectorstore, chat_llm):
    vectorstore.similarity_search_with_score.return_value = [
        (
            Document(
                page_content="Auszug",
                metadata={
                    "citation_label": "Ein Titel",
                    "page": 3,
                    "dokumentnummer": "19/1",
                    "source_url": "https://example.org/19_1.pdf",
                },
            ),
            0.25,
        )
    ]

    response = client.post("/api/ask", json={"question": "Worum geht es?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer_text"] == "Die Antwort."
    assert len(body["sources"]) == 1
    source = body["sources"][0]
    assert source["index"] == 1
    assert "Ein Titel" in source["citation"]
    assert source["text"] == "Auszug"
    assert source["page"] == 3
    assert source["source_url"] == "https://example.org/19_1.pdf"


def test_ask_returns_500_on_unexpected_error(client, vectorstore, chat_llm):
    vectorstore.similarity_search_with_score.side_effect = RuntimeError("boom")

    response = client.post("/api/ask", json={"question": "Worum geht es?"})

    assert response.status_code == 500
    assert response.json()["detail"]


def test_config_returns_language(client, settings):
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json() == {"language": settings.language}


def test_config_returns_configured_language(tmp_path, settings):
    english_settings = Settings(
        mistral_api_key="test-mistral-key",
        dip_api_key="test-dip-key",
        data_dir=tmp_path / "data",
        language="en",
        _env_file=None,
    )
    try:
        client = TestClient(create_app(settings=english_settings))

        response = client.get("/api/config")

        assert response.status_code == 200
        assert response.json() == {"language": "en"}
    finally:
        # create_app set the module-global language to "en"; restore it.
        set_language(settings.language)


def test_clear_requires_confirmation(client, vectorstore):
    response = client.post("/api/clear", json={"confirmed": False})

    assert response.status_code == 400
    assert response.json()["detail"] == t("confirmation_required")
    vectorstore.delete_collection.assert_not_called()


def test_clear_deletes_when_confirmed(client, settings, vectorstore):
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    response = client.post("/api/clear", json={"confirmed": True})

    assert response.status_code == 200
    assert response.json() == {"num_files": 1}
    assert not pdf_path.exists()
    vectorstore.delete_collection.assert_called_once()


def test_delete_file_requires_confirmation(client, settings, vectorstore):
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    response = client.post(
        "/api/files/delete", json={"pdf_path": str(pdf_path), "confirmed": False}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == t("confirmation_required")
    assert pdf_path.exists()
    vectorstore.delete.assert_not_called()


def test_delete_file_unknown_path_returns_404(client, vectorstore):
    response = client.post(
        "/api/files/delete", json={"pdf_path": "does_not_exist.pdf", "confirmed": True}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == t("file_not_found")
    vectorstore.delete.assert_not_called()


def test_delete_file_removes_pdf_and_chunks(client, settings, vectorstore):
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    response = client.post("/api/files/delete", json={"pdf_path": str(pdf_path), "confirmed": True})

    assert response.status_code == 204
    assert not pdf_path.exists()
    vectorstore.delete.assert_called_once_with(where={"pdf_path": str(pdf_path)})


def test_status_without_downloads_is_empty(client, vectorstore):
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json() == {
        "num_downloaded": 0,
        "num_indexed": 0,
        "num_chunks": 0,
        "num_manifest_chunks": 0,
        "pdf_size_bytes": 0,
        "vectorstore_size_bytes": 0,
        "files": [],
    }


def test_status_reports_downloaded_files_with_document_info(client, settings, vectorstore):
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")
    chunk_meta = {
        "id": "19/1-p1-0",
        "doc_id": "1",
        "dokumentnummer": "19/1",
        "citation_label": "Ein Titel",
        "datum": "2026-01-05",
        "page": 1,
        "pdf_path": str(pdf_path),
        "source_url": "https://example.org/1.pdf",
    }
    vectorstore.get.return_value = {"ids": [chunk_meta["id"]], "metadatas": [chunk_meta]}
    vectorstore._collection.count.return_value = 1

    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["num_downloaded"] == 1
    assert body["num_indexed"] == 1
    assert body["num_chunks"] == 1
    assert body["num_manifest_chunks"] == 1
    assert body["pdf_size_bytes"] == len(b"%PDF-1.4")
    assert body["files"][0]["pdf_path"].endswith("19_1.pdf")
    assert body["files"][0]["indexed"] is True
    assert body["files"][0]["kind"] == "drucksache"
    assert body["files"][0]["info"] == {
        "doc_id": "1",
        "dokumentnummer": "19/1",
        "citation_label": "Ein Titel",
        "datum": "2026-01-05",
        "source_url": "https://example.org/1.pdf",
        "num_chunks": 1,
        "num_pages": 1,
    }


def test_status_reports_pending_document_info_from_manifest(client, settings, vectorstore):
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as stream:
        writer.write(stream)
    add_pending(
        settings,
        [
            PendingDocument(
                kind="drucksache",
                pdf_path=pdf_path,
                meta={
                    "id": "1",
                    "dokumentnummer": "19/1",
                    "datum": "2026-01-05",
                    "wahlperiode": 21,
                    "titel": "Ein Titel",
                    "pdf_url": "https://example.org/1.pdf",
                },
            )
        ],
    )

    response = client.get("/api/status")

    assert response.status_code == 200
    file = response.json()["files"][0]
    assert file["indexed"] is False
    assert file["info"] == {
        "doc_id": "1",
        "dokumentnummer": "19/1",
        "citation_label": "Ein Titel",
        "datum": "2026-01-05",
        "source_url": "https://example.org/1.pdf",
        "num_chunks": None,
        "num_pages": 1,
    }


def test_status_reports_chunk_count_mismatch(client, vectorstore):
    # 5 chunks in the store but none accounted for by the manifest — the SPA
    # renders a warning from these two fields.
    vectorstore._collection.count.return_value = 5

    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["num_chunks"] == 5
    assert body["num_manifest_chunks"] == 0


def test_status_returns_500_on_unexpected_error(client, vectorstore):
    vectorstore._collection.count.side_effect = RuntimeError("boom")

    response = client.get("/api/status")

    assert response.status_code == 500
    assert response.json()["detail"]
