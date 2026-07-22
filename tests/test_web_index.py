import threading
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


def _seed_pending(settings, ids: tuple[str, ...] = ("1",)) -> None:
    entries = []
    for id_ in ids:
        meta = DocumentMeta(
            id=id_,
            dokumentnummer=f"19/{id_}",
            datum=date(2026, 1, 5),
            wahlperiode=21,
            drucksachetyp="Antrag",
            titel="Ein Titel",
            pdf_url=f"https://example.org/{id_}.pdf",
        )
        # Create the PDF on disk — pending entries whose file is missing are
        # treated as manually deleted and pruned before indexing.
        pdf_path = settings.pdf_dir / "drucksache" / f"19_{id_}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-1.4")
        entries.append(
            PendingDocument(
                kind="drucksache",
                pdf_path=pdf_path,
                meta=meta.model_dump(mode="json"),
            )
        )
    add_pending(settings, entries)


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

    assert body["result"] == {"num_documents": 0, "num_chunks": 0, "usage": None}
    vectorstore.add_documents.assert_not_called()


def test_index_processes_pending_documents(client, settings, vectorstore):
    _seed_pending(settings)
    # An already-indexed PDF: on disk but not pending.
    indexed_pdf = settings.pdf_dir / "drucksache" / "19_9.pdf"
    indexed_pdf.parent.mkdir(parents=True, exist_ok=True)
    indexed_pdf.write_bytes(b"%PDF-1.4")

    job_id = _start(client)

    body = _poll_job(client, job_id, lambda b: b["status"] == "done")
    assert body["counts"] == {"num_to_index": 1, "num_indexed": 1}
    assert body["result"] == {"num_documents": 1, "num_chunks": 1, "usage": None}
    assert body["progress"] == {"current": 1, "total": 1}
    vectorstore.add_documents.assert_called_once()
    assert load_pending(settings) == []


def test_index_reports_error_when_vectorstore_fails(client, settings, vectorstore):
    _seed_pending(settings)
    vectorstore.add_documents.side_effect = RuntimeError("boom")

    job_id = _start(client)

    body = _poll_job(client, job_id, lambda b: b["status"] == "error")
    assert body["error"] == "boom"
    assert len(load_pending(settings)) == 1


def test_cancel_running_index_job_leaves_remaining_documents_pending(client, settings, vectorstore):
    _seed_pending(settings, ids=("1", "2"))
    first_document_started = threading.Event()
    proceed = threading.Event()

    def add_documents(chunks, **kwargs):
        first_document_started.set()
        assert proceed.wait(timeout=5.0)

    vectorstore.add_documents.side_effect = add_documents

    job_id = _start(client)
    assert first_document_started.wait(timeout=5.0)
    # Cancel while the first document is being embedded; the second one must
    # not be processed.
    response = client.post(f"/api/index/{job_id}/cancel")
    assert response.status_code == 204
    proceed.set()

    body = _poll_job(client, job_id, lambda b: b["status"] == "cancelled")
    assert body["error"] is None
    vectorstore.add_documents.assert_called_once()
    pending = load_pending(settings)
    assert [entry.meta["id"] for entry in pending] == ["2"]


def test_cancel_unknown_index_job_returns_404(client):
    response = client.post("/api/index/unknown/cancel")

    assert response.status_code == 404


def test_get_unknown_index_job_returns_404(client):
    response = client.get("/api/index/unknown")

    assert response.status_code == 404
