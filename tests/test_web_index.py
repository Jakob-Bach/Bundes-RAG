import time
from datetime import date

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from bundesrag.dip.models import DocumentMeta
from bundesrag.ingestion import pipeline
from bundesrag.ingestion.manifest import PendingDocument, add_pending, load_pending
from bundesrag.web.app import create_app
from bundesrag.web.dependencies import get_vectorstore_dep


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


@pytest.fixture(autouse=True)
def fake_chunking(mocker):
    mocker.patch.object(
        pipeline,
        "load_pdf_as_chunks",
        return_value=[Document(page_content="text", metadata={"id": "19/1-p1-0"})],
    )


def _seed_pending(settings) -> None:
    meta = DocumentMeta(
        id="1",
        dokumentnummer="19/1",
        datum=date(2026, 1, 5),
        wahlperiode=21,
        drucksachetyp="Antrag",
        titel="Ein Titel",
        pdf_url="https://example.org/1.pdf",
    )
    add_pending(
        settings,
        [
            PendingDocument(
                kind="drucksache",
                pdf_path=settings.pdf_dir / "drucksache" / "19_1.pdf",
                meta=meta.model_dump(mode="json"),
            )
        ],
    )


def _poll_job(client, job_id, until, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/index/{job_id}").json()
        if until(body):
            return body
        time.sleep(0.01)
    pytest.fail(f"timed out waiting for job condition, last state: {body}")


def _start(client) -> str:
    response = client.post("/api/index")
    assert response.status_code == 202
    return response.json()["id"]


def test_index_without_pending_documents(client, vectorstore):
    job_id = _start(client)

    body = _poll_job(client, job_id, lambda b: b["status"] == "done")

    assert body["result"] == {"num_documents": 0, "num_chunks": 0}
    vectorstore.add_documents.assert_not_called()


def test_index_processes_pending_documents(client, settings, vectorstore):
    _seed_pending(settings)

    job_id = _start(client)

    body = _poll_job(client, job_id, lambda b: b["status"] == "done")
    assert body["result"] == {"num_documents": 1, "num_chunks": 1}
    vectorstore.add_documents.assert_called_once()
    assert load_pending(settings) == []


def test_index_reports_error_when_vectorstore_fails(client, settings, vectorstore):
    _seed_pending(settings)
    vectorstore.add_documents.side_effect = RuntimeError("boom")

    job_id = _start(client)

    body = _poll_job(client, job_id, lambda b: b["status"] == "error")
    assert body["error"] == "boom"
    assert len(load_pending(settings)) == 1


def test_get_unknown_index_job_returns_404(client):
    response = client.get("/api/index/unknown")

    assert response.status_code == 404
