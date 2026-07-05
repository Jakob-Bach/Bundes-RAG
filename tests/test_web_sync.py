import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from bundesrag.config import Settings
from bundesrag.i18n import set_language, t
from bundesrag.web.app import create_app
from bundesrag.web.dependencies import get_chat_llm, get_vectorstore_dep


@pytest.fixture
def app(settings):
    return create_app(settings=settings)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def vectorstore(app, mocker):
    store = mocker.Mock()
    app.dependency_overrides[get_vectorstore_dep] = lambda: store
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
                metadata={"citation_label": "Ein Titel", "page": 3, "dokumentnummer": "19/1"},
            ),
            0.25,
        )
    ]

    response = client.post("/api/ask", json={"question": "Worum geht es?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer_text"] == "Die Antwort."
    assert len(body["sources"]) == 1
    assert "Ein Titel" in body["sources"][0]


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


def test_status_without_downloads_is_empty(client):
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json() == {"num_downloaded": 0, "num_indexed": 0, "files": []}


def test_status_reports_downloaded_files(client, settings):
    pdf_path = settings.pdf_dir / "drucksache" / "19_1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["num_downloaded"] == 1
    assert body["num_indexed"] == 1
    assert body["files"][0]["pdf_path"].endswith("19_1.pdf")
    assert body["files"][0]["indexed"] is True
