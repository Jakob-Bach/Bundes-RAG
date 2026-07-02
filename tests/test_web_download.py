import time
from datetime import date

import pytest
from fastapi.testclient import TestClient

from bundesrag.dip.models import DocumentMeta
from bundesrag.ingestion.manifest import load_pending
from bundesrag.query_agent.schema import DipQueryFilters
from bundesrag.web.app import create_app
from bundesrag.web.dependencies import get_dip_client, get_query_agent

FILTERS = DipQueryFilters(endpoint="drucksache", wahlperiode=21)


def _drucksache_meta(id_: str = "1", day: int = 5) -> DocumentMeta:
    return DocumentMeta(
        id=id_,
        dokumentnummer=f"19/{id_}",
        datum=date(2026, 1, day),
        wahlperiode=21,
        drucksachetyp="Antrag",
        titel="Ein Titel",
        pdf_url=f"https://example.org/{id_}.pdf",
    )


@pytest.fixture
def app(settings):
    return create_app(settings=settings)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def query_agent(app, mocker):
    agent = mocker.Mock()
    agent.build_query.return_value = FILTERS
    app.dependency_overrides[get_query_agent] = lambda: agent
    return agent


@pytest.fixture
def dip_client(app, mocker):
    dip = mocker.Mock()
    dip.list_drucksachen.return_value = [_drucksache_meta("1")]
    dip.list_plenarprotokolle.return_value = []
    dip.download_pdf.side_effect = lambda url, dest: dest
    app.dependency_overrides[get_dip_client] = lambda: dip
    return dip


def _poll_job(client, job_id, until, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/download/{job_id}").json()
        if until(body):
            return body
        time.sleep(0.01)
    pytest.fail(f"timed out waiting for job condition, last state: {body}")


def _start(client, prompt="Drucksachen der 21. Wahlperiode."):
    response = client.post("/api/download", json={"prompt": prompt})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] in ("running", "waiting_input")
    return body["id"]


def test_download_happy_path(client, settings, query_agent, dip_client):
    job_id = _start(client)

    body = _poll_job(client, job_id, lambda b: b["status"] == "waiting_input")
    assert body["pending"]["kind"] == "confirm_count"
    assert body["pending"]["count"] == 1

    response = client.post(f"/api/download/{job_id}/respond", json={"answer": "1"})
    assert response.status_code == 204

    body = _poll_job(client, job_id, lambda b: b["status"] == "done")
    assert body["result"] == {"num_documents": 1, "num_failed": 0}
    assert len(load_pending(settings)) == 1
    dip_client.close.assert_called_once()


def test_download_confirm_filters_round_trip(client, query_agent, dip_client):
    def fake_build_query(nl_prompt, ask_user, confirm_filters):
        assert confirm_filters(FILTERS) is True
        return FILTERS

    query_agent.build_query.side_effect = fake_build_query
    job_id = _start(client)

    body = _poll_job(client, job_id, lambda b: b["status"] == "waiting_input")
    assert body["pending"]["kind"] == "confirm_filters"
    assert "drucksache" in body["pending"]["filters_text"]

    client.post(f"/api/download/{job_id}/respond", json={"answer": "true"})
    body = _poll_job(
        client,
        job_id,
        lambda b: b["status"] == "waiting_input" and b["pending"]["kind"] == "confirm_count",
    )
    client.post(f"/api/download/{job_id}/respond", json={"answer": "1"})

    body = _poll_job(client, job_id, lambda b: b["status"] == "done")
    assert body["result"]["num_documents"] == 1


def test_download_ask_user_round_trip(client, query_agent, dip_client):
    def fake_build_query(nl_prompt, ask_user, confirm_filters):
        assert ask_user("Welche Wahlperiode?") == "die 21."
        return FILTERS

    query_agent.build_query.side_effect = fake_build_query
    job_id = _start(client)

    body = _poll_job(client, job_id, lambda b: b["status"] == "waiting_input")
    assert body["pending"]["kind"] == "ask_user"
    assert body["pending"]["question"] == "Welche Wahlperiode?"

    client.post(f"/api/download/{job_id}/respond", json={"answer": "die 21."})
    _poll_job(
        client,
        job_id,
        lambda b: b["status"] == "waiting_input" and b["pending"]["kind"] == "confirm_count",
    )
    client.post(f"/api/download/{job_id}/respond", json={"answer": "1"})

    _poll_job(client, job_id, lambda b: b["status"] == "done")


def test_download_limits_to_most_recent_documents(client, settings, query_agent, dip_client):
    dip_client.list_drucksachen.return_value = [
        _drucksache_meta("1", day=1),
        _drucksache_meta("2", day=10),
        _drucksache_meta("3", day=5),
    ]
    job_id = _start(client)

    body = _poll_job(client, job_id, lambda b: b["status"] == "waiting_input")
    assert body["pending"]["count"] == 3

    client.post(f"/api/download/{job_id}/respond", json={"answer": "2"})

    body = _poll_job(client, job_id, lambda b: b["status"] == "done")
    assert body["result"]["num_documents"] == 2
    pending = load_pending(settings)
    assert {entry.meta["id"] for entry in pending} == {"2", "3"}


def test_download_aborts_when_user_answers_zero(client, settings, query_agent, dip_client):
    job_id = _start(client)

    _poll_job(client, job_id, lambda b: b["status"] == "waiting_input")
    client.post(f"/api/download/{job_id}/respond", json={"answer": "0"})

    body = _poll_job(client, job_id, lambda b: b["status"] == "error")
    assert body["error"]
    dip_client.download_pdf.assert_not_called()
    assert load_pending(settings) == []


def test_respond_rejects_non_integer_count_answer(client, query_agent, dip_client):
    job_id = _start(client)
    _poll_job(client, job_id, lambda b: b["status"] == "waiting_input")

    response = client.post(f"/api/download/{job_id}/respond", json={"answer": "viele"})

    assert response.status_code == 400
    # The job is still waiting and can be answered properly afterwards.
    client.post(f"/api/download/{job_id}/respond", json={"answer": "1"})
    _poll_job(client, job_id, lambda b: b["status"] == "done")


def test_respond_to_unknown_job_returns_404(client):
    response = client.post("/api/download/unknown/respond", json={"answer": "1"})

    assert response.status_code == 404


def test_respond_to_finished_job_returns_409(client, query_agent, dip_client):
    job_id = _start(client)
    _poll_job(client, job_id, lambda b: b["status"] == "waiting_input")
    client.post(f"/api/download/{job_id}/respond", json={"answer": "1"})
    _poll_job(client, job_id, lambda b: b["status"] == "done")

    response = client.post(f"/api/download/{job_id}/respond", json={"answer": "1"})

    assert response.status_code == 409


def test_get_unknown_download_job_returns_404(client):
    response = client.get("/api/download/unknown")

    assert response.status_code == 404
